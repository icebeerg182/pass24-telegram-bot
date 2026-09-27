import re
from dataclasses import dataclass

from .brands import resolve_brand, suggest_brands

_PLATE_LETTERS = r"[авекмнорстухabekmhopctyx]"

# Полный госномер: буква + 3 цифры + 2 буквы + регион (2–3)
PLATE_FULL_RE = re.compile(
    rf"(?i)"
    rf"({_PLATE_LETTERS})"
    rf"\s*(\d{{3}})"
    rf"\s*({_PLATE_LETTERS}{{2}})"
    rf"\s*(\d{{2,3}})"
)

# Без региона: буква + 3 цифры + 2 буквы (А121МР)
PLATE_SHORT_RE = re.compile(
    rf"(?i)"
    rf"({_PLATE_LETTERS})"
    rf"\s*(\d{{3}})"
    rf"\s*({_PLATE_LETTERS}{{2}})"
    rf"(?!\s*\d)"  # не съедать хвост полного номера
)

# Совместимость со старым именем
PLATE_FLEX_RE = PLATE_FULL_RE

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
    # мусор из Wheely / детальных названий
    "класс", "class", "klasse", "серии", "series", "serie",
    "купе", "coupe", "седан", "sedan", "универсал",
    "кабриолет", "cabriolet", "внедорожник", "кроссовер",
}

# S-Класс, E-Class, GLE-Класс, S Class…
_CLASS_TOKEN_RE = re.compile(
    r"(?i)^(?:[a-zа-я]{1,4}-?)?(?:класс|class|klasse)$"
)
# Коды кузова/поколений: Z223, W223, V223, X167…
_CHASSIS_CODE_RE = re.compile(r"(?i)^[a-z]\d{2,3}[a-z]?$")
# Короткие модельные индексы без марки: 223, 350d — не марка
_BARE_MODEL_NUM_RE = re.compile(r"(?i)^\d{2,4}[a-z]?$")


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
    # Wheely часто шлёт «модель, номер»
    text = text.replace(",", " ")
    return re.sub(r"\s+", " ", text).strip()


def _is_ignored_token(token: str) -> bool:
    t = token.lower().strip(".,;:·•")
    if not t:
        return True
    if t in IGNORE_TOKENS:
        return True
    if _CLASS_TOKEN_RE.fullmatch(t):
        return True
    if _CHASSIS_CODE_RE.fullmatch(t):
        return True
    if _BARE_MODEL_NUM_RE.fullmatch(t):
        return True
    return False


def _expand_token_candidates(token: str) -> list[str]:
    """Mercedes-Maybach → Mercedes-Maybach, Mercedes, Maybach (сначала целое и левая часть)."""
    token = token.strip(".,;:·•")
    if not token:
        return []
    out: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        v = value.strip("-_. ")
        if not v or _is_ignored_token(v):
            return
        key = v.lower()
        if key in seen:
            return
        seen.add(key)
        out.append(v)

    parts = [p for p in re.split(r"[-_/]+", token) if p]
    # Сначала целое (алиас mercedes-maybach → Mercedes), затем слева направо
    add(token)
    for part in parts:
        add(part)
    return out


def _extract_brand_tokens(text: str, plate_match: re.Match) -> list[str]:
    before = text[: plate_match.start()].strip()
    after = text[plate_match.end() :].strip()
    tokens: list[str] = []

    for part in (before, after):
        if not part:
            continue
        for raw in re.split(r"[\s,]+", part):
            token = raw.strip(".,;:·•")
            if not token or _is_ignored_token(token):
                continue
            compact = re.sub(r"\s+", "", token)
            if PLATE_FULL_RE.fullmatch(compact) or PLATE_SHORT_RE.fullmatch(compact):
                continue
            tokens.append(token)

    return tokens


def _candidate_brand_strings(tokens: list[str]) -> list[str]:
    """Плоский список кандидатов марки из токенов Wheely/ручного ввода."""
    candidates: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        key = value.lower()
        if key in seen:
            return
        seen.add(key)
        candidates.append(value)

    # Составные пары целиком (Land Rover)
    for i in range(len(tokens) - 1):
        add(f"{tokens[i]} {tokens[i + 1]}")

    for token in tokens:
        for cand in _expand_token_candidates(token):
            add(cand)

    return candidates


def resolve_brand_from_verbose_name(
    vehicle_name: str,
    pass24_models: dict[str, int],
) -> tuple[str, str] | None:
    """Разобрать длинное имя вроде «Mercedes-Maybach S-Класс Z223» → марка PASS24."""
    text = _normalize_text(vehicle_name)
    if not text:
        return None
    tokens = [
        t for t in re.split(r"[\s,]+", text)
        if t and not _is_ignored_token(t.strip(".,;:·•"))
    ]
    if not tokens:
        return None
    for cand in _candidate_brand_strings(tokens):
        found = resolve_brand(cand, pass24_models)
        if found:
            return cand, found

    from bot.llm_brand import resolve_brand_via_llm

    llm_brand = resolve_brand_via_llm(text, pass24_models)
    if llm_brand:
        return text, llm_brand
    return None


def find_plate_match(
    text: str,
    *,
    require_full_plate: bool = True,
) -> re.Match | None:
    """Найти госномер: полный или (если разрешено) без региона."""
    match = PLATE_FULL_RE.search(text)
    if match:
        return match
    if not require_full_plate:
        return PLATE_SHORT_RE.search(text)
    return None


def plate_format_hint(*, require_full_plate: bool = True) -> str:
    if require_full_plate:
        return (
            "Формат: буква + 3 цифры + 2 буквы + регион\n"
            "Примеры: А121МР777, BMW А121МР77, А121МР77 BMW"
        )
    return (
        "Формат: буква + 3 цифры + 2 буквы (регион необязателен)\n"
        "Примеры: А121МР, BMW А121МР77, мерс А 121 МР"
    )


def parse_message(
    text: str,
    pass24_models: dict[str, int],
    *,
    require_full_plate: bool = True,
) -> ParsedPass:
    text = _normalize_text(text)
    if not text:
        raise ParseError("Пустое сообщение")

    match = find_plate_match(text, require_full_plate=require_full_plate)
    if not match:
        prefix = (
            "Не найден полный госномер.\n"
            if require_full_plate
            else "Не найден госномер.\n"
        )
        raise ParseError(prefix + plate_format_hint(require_full_plate=require_full_plate))

    plate = normalize_plate("".join(match.groups()))
    tokens = _extract_brand_tokens(text, match)

    if not tokens:
        raise ParseError(
            "Укажите марку автомобиля рядом с номером.\n"
            "Примеры: мерс А121МР777, А121МР77 BMW, BMW А121МР77 серый"
        )

    canonical = None
    brand_token = None

    for cand in _candidate_brand_strings(tokens):
        found = resolve_brand(cand, pass24_models)
        if found:
            canonical = found
            brand_token = cand
            break

    if not canonical:
        from bot.llm_brand import resolve_brand_via_llm

        # В LLM отдаём исходный фрагмент с маркой (без опоры только на токены)
        brand_side = (text[: match.start()] + " " + text[match.end() :]).strip()
        llm_brand = resolve_brand_via_llm(brand_side or text, pass24_models)
        if llm_brand:
            canonical = llm_brand
            brand_token = brand_side or tokens[0]

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
