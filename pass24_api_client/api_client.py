import os
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

    def __init__(
        self,
        phone: str,
        password: str,
        address_keyword: str | None = None,
        vehicle_type_keyword: str | None = None,
        vehicle_type_id: int | None = None,
    ):
        self.phone = phone
        self.password = password
        self.address_keyword = address_keyword
        self.vehicle_type_keyword = vehicle_type_keyword or os.getenv(
            "PASS24_VEHICLE_TYPE_KEYWORD", "легков"
        )
        self._vehicle_type_id_override = vehicle_type_id
        if self._vehicle_type_id_override is None:
            raw = os.getenv("PASS24_VEHICLE_TYPE_ID", "").strip()
            if raw.isdigit():
                self._vehicle_type_id_override = int(raw)
        self.token: str | None = None
        self.vehicle_models: dict[str, int] | None = None
        self.vehicle_types: dict[str, int] | None = None
        self._address_id: int | None = None
        self._address_record: dict | None = None

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

    @staticmethod
    def _merge_vehicle_types(target: dict[str, int], items) -> None:
        if not items:
            return
        if isinstance(items, dict):
            for name, vid in items.items():
                if isinstance(name, str) and isinstance(vid, int):
                    target[name] = vid
            return
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("title") or item.get("label")
            vid = item.get("id")
            if name and vid is not None:
                target[str(name)] = int(vid)

    def _collect_types_from_record(self, record: dict | None) -> dict[str, int]:
        types: dict[str, int] = {}
        if not record:
            return types
        for key in (
            "vehicleTypes",
            "transportTypes",
            "vehicle_types",
            "transport_types",
            "types",
        ):
            self._merge_vehicle_types(types, record.get(key))
        for nested_key in ("object", "tenant", "settings", "passSettings", "options"):
            nested = record.get(nested_key)
            if isinstance(nested, dict):
                for key in (
                    "vehicleTypes",
                    "transportTypes",
                    "vehicle_types",
                    "transport_types",
                    "types",
                ):
                    self._merge_vehicle_types(types, nested.get(key))
        return types

    def _match_addresses(self, addresses: list[dict]) -> list[dict]:
        if not self.address_keyword:
            return addresses[:1]
        keyword = self.address_keyword.lower()
        matched = [
            a for a in addresses
            if keyword in (a.get("name") or "").lower()
            or keyword in (a.get("object", {}).get("name") or "").lower()
        ]
        return matched or []

    def _get_address_record(self) -> dict:
        if self._address_record is not None:
            return self._address_record

        json_data = self.get("profile/addresses")
        if json_data.get("error"):
            raise RequestError(json_data["error"])

        addresses = json_data.get("body") or []
        if not addresses:
            raise AddressError("Нет привязанных адресов")

        if self.address_keyword:
            matched = self._match_addresses(addresses)
            if not matched:
                names = ", ".join(a.get("name", "?") for a in addresses)
                raise AddressError(
                    f'Адрес с «{self.address_keyword}» не найден. Доступны: {names}'
                )
            self._address_record = matched[0]
        else:
            self._address_record = addresses[0]

        return self._address_record

    def get_vehicle_types(self) -> dict[str, int]:
        if self.vehicle_types is not None:
            return self.vehicle_types

        types: dict[str, int] = {}

        # 1. Типы из выбранного адреса (как в мобильном приложении).
        try:
            addr = self._get_address_record()
            types.update(self._collect_types_from_record(addr))
        except (AddressError, RequestError):
            pass

        # 2. Типы из объекта, привязанного к адресу.
        if not types:
            try:
                addr = self._get_address_record()
                object_id = (
                    addr.get("objectId")
                    or addr.get("object", {}).get("id")
                )
                json_data = self.get("profile/objects")
                if not json_data.get("error"):
                    for obj in json_data.get("body") or []:
                        if object_id is not None and obj.get("id") != object_id:
                            continue
                        if self.address_keyword:
                            keyword = self.address_keyword.lower()
                            obj_name = (obj.get("name") or "").lower()
                            if keyword not in obj_name and object_id is None:
                                continue
                        types.update(self._collect_types_from_record(obj))
                        if types:
                            break
            except (ResponseStatusError, RequestError):
                pass

        # 3. Эндпоинты с привязкой к addressId.
        if not types:
            try:
                addr_id = self.get_address_id()
                for path in (
                    "passes/vehicle-types",
                    "passes/transport-types",
                    "vehicle-types/by-address",
                ):
                    try:
                        json_data = self.post(path, {"addressId": addr_id})
                        if not json_data.get("error") and json_data.get("body"):
                            self._merge_vehicle_types(types, json_data["body"])
                            break
                    except ResponseStatusError:
                        pass
            except (AddressError, RequestError):
                pass

        # 3b. Из недавних пропусков (если в приложении уже заказывали).
        if not types:
            try:
                json_data = self.get("passes")
                if not json_data.get("error"):
                    for p in json_data.get("body") or []:
                        guest = p.get("guestData") or {}
                        vt = guest.get("vehicleType")
                        if isinstance(vt, dict):
                            name = vt.get("name")
                            vid = vt.get("id")
                        else:
                            vid = vt
                            name = (
                                (guest.get("vehicleTypeName") or guest.get("transportTypeName"))
                                if vid is not None
                                else None
                            )
                        if vid is not None and name:
                            types[str(name)] = int(vid)
                        elif vid is not None:
                            types[f"type_{vid}"] = int(vid)
                        if types:
                            break
            except (ResponseStatusError, RequestError):
                pass

        # 4. Глобальный справочник — только если объектные типы не найдены.
        if not types:
            for path in ("vehicle-types", "vehicleTypes", "transport-types"):
                try:
                    json_data = self.get(path, body=None, need_token=False)
                    if not json_data.get("error") and json_data.get("body"):
                        self._merge_vehicle_types(types, json_data["body"])
                        break
                except ResponseStatusError:
                    pass
                try:
                    json_data = self.get(path, body=None, need_token=True)
                    if not json_data.get("error") and json_data.get("body"):
                        self._merge_vehicle_types(types, json_data["body"])
                        break
                except ResponseStatusError:
                    pass

        self.vehicle_types = types
        return self.vehicle_types

    def resolve_vehicle_type_id(self, keyword: str | None = None) -> int:
        if self._vehicle_type_id_override is not None and keyword is None:
            return self._vehicle_type_id_override

        types = self.get_vehicle_types()
        if not types:
            raise RequestError(
                "Не удалось получить типы ТС для адреса из PASS24. "
                "Запустите: python deploy/discover_types.py "
                "и задайте PASS24_VEHICLE_TYPE_ID в .env."
            )

        search = (keyword or self.vehicle_type_keyword or "легков").lower()
        for name, vid in types.items():
            if search in name.lower():
                return vid

        # частые названия
        for name, vid in types.items():
            low = name.lower()
            if search.startswith("груз"):
                if "груз" in low or "truck" in low or "freight" in low:
                    return vid
            elif "легков" in low or low == "car" or "passenger" in low:
                return vid

        names = ", ".join(f"{name} ({vid})" for name, vid in types.items())
        raise RequestError(
            f'Тип ТС «{search}» не найден. Доступны: {names}'
        )

    def resolve_model_id(self, brand_name: str) -> int | None:
        models = self.get_vehicle_models()
        if brand_name in models:
            return models[brand_name]
        lower_map = {k.lower(): v for k, v in models.items()}
        return lower_map.get(brand_name.lower())

    def get_address_id(self) -> int:
        if self._address_id is not None:
            return self._address_id

        self._address_id = self._get_address_record()["id"]
        return self._address_id

    def get_address_name(self) -> str:
        addr = self._get_address_record()
        return addr.get("name", "—")

    def create_pass(
        self,
        plate_number: str,
        vehicle_model: str,
        expiration_hours: int = 24,
        vehicle_type_keyword: str | None = None,
    ) -> dict:
        model_id = self.resolve_model_id(vehicle_model)
        if not model_id:
            model_id = self.resolve_model_id("Не задана")
        if not model_id:
            raise RequestError(f"Марка «{vehicle_model}» не найдена в справочнике PASS24")

        vehicle_type_id = self.resolve_vehicle_type_id(keyword=vehicle_type_keyword)

        starts_at = datetime.datetime.now(MSK) + datetime.timedelta(minutes=1)
        expires_at = starts_at + datetime.timedelta(hours=expiration_hours)

        body = {
            "addressId": self.get_address_id(),
            "durationType": 1,
            "guestType": 1,
            "guestData": {
                "vehicleType": vehicle_type_id,
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
