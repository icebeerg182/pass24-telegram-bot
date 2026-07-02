import base64
import datetime
import json
from enum import Enum
from http import HTTPStatus

import pytz
import requests

MSK = pytz.timezone("Europe/Moscow")


class RequestMethod(Enum):
    GET = "get"
    POST = "post"


class AuthError(Exception):
    pass


class AddressError(Exception):
    pass


class ResponseStatusError(Exception):
    pass


class RequestError(Exception):
    pass


def _jwt_expired(token: str, skew_seconds: int = 120) -> bool:
    try:
        payload_b64 = token.split(".")[1]
        padding = "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
        exp = payload.get("exp")
        if not exp:
            return False
        return datetime.datetime.now(datetime.timezone.utc).timestamp() >= exp - skew_seconds
    except (IndexError, json.JSONDecodeError, ValueError):
        return False


class Pass24ApiClient:
    BASE_URL = "https://mobile-api.pass24online.ru/v1/"

    def __init__(self, phone: str, password: str, address_keyword: str | None = None):
        self.phone = phone
        self.password = password
        self.address_keyword = address_keyword
        self.token: str | None = None
        self.vehicle_models: dict[str, int] | None = None
        self._address_id: int | None = None

    def invalidate_token(self) -> None:
        self.token = None

    def login(self) -> str:
        body = {"phone": self.phone, "password": self.password}
        json_data = self.post("auth/login", body, need_token=False)
        if json_data.get("error"):
            raise AuthError(json_data["error"])
        self.token = json_data["body"]
        return self.token

    def get_token(self, force_refresh: bool = False) -> str:
        if force_refresh or not self.token or _jwt_expired(self.token):
            return self.login()
        return self.token

    def get(self, path, body=None, need_token=True, ok_status=HTTPStatus.OK, as_json=True, retry_auth=True):
        return self.request(RequestMethod.GET, path, body, need_token, ok_status, as_json, retry_auth)

    def post(self, path, body=None, need_token=True, ok_status=HTTPStatus.OK, as_json=True, retry_auth=True):
        return self.request(RequestMethod.POST, path, body, need_token, ok_status, as_json, retry_auth)

    def request(self, method, path, body, need_token, ok_status, as_json, retry_auth=True):
        url = self.BASE_URL + path
        if need_token:
            if body is None:
                body = {}
            body = dict(body)
            body["token"] = self.get_token()

        if method == RequestMethod.GET:
            response = requests.get(url, json=body, timeout=30)
        elif method == RequestMethod.POST:
            response = requests.post(url, json=body, timeout=30)
        else:
            raise ValueError(f"Unknown method: {method}")

        if response.status_code == HTTPStatus.UNAUTHORIZED and need_token and retry_auth:
            self.invalidate_token()
            return self.request(method, path, body, need_token, ok_status, as_json, retry_auth=False)

        if ok_status and response.status_code != ok_status:
            raise ResponseStatusError(
                f"HTTP {response.status_code}: {response.text[:500]}"
            )

        if as_json:
            data = response.json()
            if need_token and retry_auth and data.get("error"):
                err = data["error"]
                code = err.get("code", "") if isinstance(err, dict) else str(err)
                if "TOKEN" in str(code).upper() or "AUTH" in str(code).upper():
                    self.invalidate_token()
                    return self.request(method, path, body, need_token, ok_status, as_json, retry_auth=False)
            return data
        return response

    def get_vehicle_models(self) -> dict[str, int]:
        if not self.vehicle_models:
            json_data = self.get("vehicle-models", body=None, need_token=False)
            if json_data.get("error"):
                raise RequestError(json_data["error"])
            self.vehicle_models = {
                m["name"]: m["id"] for m in json_data["body"]
            }
        return self.vehicle_models

    def resolve_model_id(self, brand_name: str) -> int | None:
        models = self.get_vehicle_models()
        if brand_name in models:
            return models[brand_name]
        lower_map = {k.lower(): v for k, v in models.items()}
        return lower_map.get(brand_name.lower())

    def get_address_id(self) -> int:
        if self._address_id is not None:
            return self._address_id

        json_data = self.get("profile/addresses")
        if json_data.get("error"):
            raise RequestError(json_data["error"])

        addresses = json_data.get("body") or []
        if not addresses:
            raise AddressError("Нет привязанных адресов")

        if self.address_keyword:
            keyword = self.address_keyword.lower()
            matched = [
                a for a in addresses
                if keyword in (a.get("name") or "").lower()
                or keyword in (a.get("object", {}).get("name") or "").lower()
            ]
            if not matched:
                names = ", ".join(a.get("name", "?") for a in addresses)
                raise AddressError(
                    f'Адрес с «{self.address_keyword}» не найден. Доступны: {names}'
                )
            self._address_id = matched[0]["id"]
            return self._address_id

        self._address_id = addresses[0]["id"]
        return self._address_id

    def get_address_name(self) -> str:
        json_data = self.get("profile/addresses")
        addresses = json_data.get("body") or []
        addr_id = self.get_address_id()
        for a in addresses:
            if a["id"] == addr_id:
                return a.get("name", "—")
        return "—"

    def create_pass(
        self,
        plate_number: str,
        vehicle_model: str,
        expiration_hours: int = 24,
    ) -> dict:
        model_id = self.resolve_model_id(vehicle_model)
        if not model_id:
            model_id = self.resolve_model_id("Не задана")
        if not model_id:
            raise RequestError(f"Марка «{vehicle_model}» не найдена в справочнике PASS24")

        starts_at = datetime.datetime.now(MSK) + datetime.timedelta(minutes=1)
        expires_at = starts_at + datetime.timedelta(hours=expiration_hours)

        body = {
            "addressId": self.get_address_id(),
            "durationType": 1,
            "guestType": 1,
            "guestData": {
                "vehicleType": None,
                "modelId": model_id,
                "plateNumber": plate_number,
            },
            "startsAt": starts_at.strftime("%Y-%m-%d %H:%M:%S"),
            "expiresAt": expires_at.strftime("%Y-%m-%d %H:%M:%S"),
            "options": [None],
        }
        json_data = self.post("passes", body)
        if json_data.get("error"):
            raise RequestError(json_data["error"])
        return json_data["body"]
