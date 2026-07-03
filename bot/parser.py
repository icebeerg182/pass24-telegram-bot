import re
from dataclasses import dataclass

from .brands import resolve_brand, suggest_brands

# Госномер с необязательными пробелами между частями
PLATE_FLEX_RE = re.compile(
    r"(?i)"
    r"([авекмнорстухabekmhopctyx])"
    r"\s*(\d{3})"
    r"\s*([авекмнорстухabekmhopctyx]{2})"
    r"\s*(\d{2,3})"
)

CYR_TO_LAT = str.maketrans("АВЕКМНОРСТУХ", "ABEKMHOPCTYX")
LAT_TO_CYR = str.maketrans("ABEKMHOPCTYX", "АВЕКМНОРСТУХ")

# Цвет и прочие слова, не являющиеся маркой
IGNORE_TOKENS = {
    "серый", "серая", "серое", "серый.", "grey", "gray",
    "белый", "белая", "белое", "white",
    "черный", "чёрный", "черная", "чёрная", "black",
    "красный", "красная", "red",
    "синий", "синяя", "blue",
    "зеленый", "зелёный", "зеленая", "green",
    "желтый", "жёлтый", "yellow",
    "коричневый", "brown",
    "серебристый", "silver",
    "бежевый", "beige",
    "оранжевый", "orange",
    "фиолетовый", "purple",
    "голубой", "lightblue",
}


@dataclass
class ParsedPass:
    brand_token: str
    brand_canonical: str
    plate: str


class ParseError(Exception):
    pass


def normalize_plate(raw: str) -> str:
    s = raw.upper().replace(" ", "").replace("-", "")
    if re.search(r"[A-Z]", s) and not re.search(r"[А-Я]", s):
        s = s.translate(LAT_TO_CYR)
    elif re.search(r"[А-Я]", s):
        s = s.translate(CYR_TO_LAT).translate(LAT_TO_CYR)
    else:
        s = s.translate(LAT_TO_CYR)
    return s


def _normalize_text(text: str) -> str:
    text = (text or "").strip()
    text = text.replace("\n", " ").replace("\r", " ")
    return re.sub(r"\s+", " ", text).strip()


def _is_ignored_token(token: str) -> bool:
    return token.lower().strip(".,;:") in IGNORE_TOKENS


def _extract_brand_tokens(text: str, plate_match: re.Match) -> list[str]:
    before = text[: plate_match.start()].strip()
    after = text[plate_match.end() :].strip()
    tokens: list[str] = []

    for part in (before, after):
        if not part:
            continue
        for raw in re.split(r"[\s,]+", part):
            token = raw.strip(".,;:")
            if not token or _is_ignored_token(token):
                continue
            compact = re.sub(r"\s+", "", token)
            if PLATE_FLEX_RE.fullmatch(compact):
                continue
            tokens.append(token)

    return tokens


def parse_message(text: str, pass24_models: dict[str, int]) -> ParsedPass:
    text = _normalize_text(text)
    if not text:
        raise ParseError("Пустое сообщение")

    match = PLATE_FLEX_RE.search(text)
    if not match:
        raise ParseError(
            "Не найден полный госномер.\n"
            "Формат: буква + 3 цифры + 2 буквы + регион\n"
            "Примеры: А121МР777, BMW А121МР77, А121МР77 BMW"
        )

    plate = normalize_plate("".join(match.groups()))
    tokens = _extract_brand_tokens(text, match)

    if not tokens:
        raise ParseError(
            "Укажите марку автомобиля рядом с номером.\n"
            "Примеры: мерс А121МР777, А121МР77 BMW, BMW А121МР77 серый"
        )

    canonical = None
    brand_token = None

    for token in tokens:
        found = resolve_brand(token, pass24_models)
        if found:
            canonical = found
            brand_token = token
            break

    # Составные марки: land rover, mercedes benz
    if not canonical and len(tokens) >= 2:
        for i in range(len(tokens) - 1):
            pair = f"{tokens[i]} {tokens[i + 1]}"
            found = resolve_brand(pair, pass24_models)
            if found:
                canonical = found
                brand_token = pair
                break

    if not canonical:
        hints = suggest_brands(tokens[0], pass24_models)
        extra = ""
        if hints:
            extra = "\n\nВозможно: " + ", ".join(hints)
        raise ParseError(
            f"Не удалось определить марку из «{' '.join(tokens)}».\n"
            "Укажите марку как в PASS24 (BMW, Mercedes-Benz, Lada…)."
            f"{extra}"
        )

    return ParsedPass(
        brand_token=brand_token,
        brand_canonical=canonical,
        plate=plate,
    )
