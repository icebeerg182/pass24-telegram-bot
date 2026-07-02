import re
from dataclasses import dataclass

from .brands import resolve_brand

PLATE_RE = re.compile(
    r"(?i)([авекмнорстухabekmhopctyx]\d{3}[авекмнорстухabekmhopctyx]{2}\d{2,3})"
)

CYR_TO_LAT = str.maketrans("АВЕКМНОРСТУХ", "ABEKMHOPCTYX")
LAT_TO_CYR = str.maketrans("ABEKMHOPCTYX", "АВЕКМНОРСТУХ")


@dataclass
class ParsedPass:
    brand_token: str
    brand_canonical: str
    plate: str


class ParseError(Exception):
    pass


def normalize_plate(raw: str) -> str:
    s = raw.upper().replace(" ", "").replace("-", "")
    if re.search(r"[А-Я]", s):
        s = s.translate(CYR_TO_LAT).translate(LAT_TO_CYR)
    else:
        s = s.translate(LAT_TO_CYR)
    return s


def parse_message(text: str, pass24_models: dict[str, int]) -> ParsedPass:
    text = (text or "").strip()
    if not text:
        raise ParseError("Пустое сообщение")

    compact = re.sub(r"\s+", "", text)
    match = PLATE_RE.search(compact)
    if not match:
        raise ParseError(
            "Не найден полный госномер.\n"
            "Формат: буква + 3 цифры + 2 буквы + регион, например А121МР777"
        )

    plate = normalize_plate(match.group(1))
    before = compact[: match.start()].strip()

    if match.end() < len(compact):
        raise ParseError("После номера не должно быть лишнего текста")

    if not before:
        raise ParseError("Укажите марку перед номером, например: мерс А121МР777")

    brand_token = before
    canonical = resolve_brand(brand_token, pass24_models)

    if not canonical:
        for part in re.split(r"[\s,]+", text):
            part = re.sub(r"\s+", "", part)
            if part and not PLATE_RE.fullmatch(part):
                canonical = resolve_brand(part, pass24_models)
                if canonical:
                    brand_token = part
                    break

    if not canonical:
        raise ParseError(
            f"Не удалось определить марку из «{before}».\n"
            "Попробуйте другое сокращение или полное название."
        )

    return ParsedPass(
        brand_token=brand_token,
        brand_canonical=canonical,
        plate=plate,
    )
