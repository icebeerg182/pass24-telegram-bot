"""Сокращения и синонимы марок → имя в справочнике PASS24."""

from __future__ import annotations

import re
import unicodedata

# Токен пользователя → варианты поиска в справочнике (по приоритету).
# Значение — строка или список подстрок/имён для сопоставления с vehicle-models.
BRAND_ALIASES: dict[str, str | list[str]] = {
    # Mercedes-Benz
    "мерс": ["mercedes-benz", "mercedes"],
    "мерседес": ["mercedes-benz", "mercedes"],
    "мерин": ["mercedes-benz", "mercedes"],
    "мерседесбенц": ["mercedes-benz", "mercedes"],
    "mb": ["mercedes-benz", "mercedes"],
    "benz": ["mercedes-benz", "mercedes"],
    # Maybach
    "майбах": "maybach",
    "maybach": "maybach",
    # BMW
    "бмв": "bmw",
    "bmw": "bmw",
    # Audi
    "ауди": "audi",
    "audi": "audi",
    # Toyota
    "тойота": "toyota",
    "toyota": "toyota",
    # Lexus
    "лексус": "lexus",
    "lexus": "lexus",
    # Volkswagen
    "фолькс": "volkswagen",
    "фольц": "volkswagen",
    "фольксваген": "volkswagen",
    "фольксвагн": "volkswagen",
    "vw": "volkswagen",
    "volkswagen": "volkswagen",
    # Hyundai
    "хендай": "hyundai",
    "хёндай": "hyundai",
    "хундай": "hyundai",
    "хенде": "hyundai",
    "хюндай": "hyundai",
    "hyundai": "hyundai",
    # Kia
    "киа": "kia",
    "kia": "kia",
    # Nissan
    "ниссан": "nissan",
    "нисан": "nissan",
    "nissan": "nissan",
    # Honda
    "хонда": "honda",
    "honda": "honda",
    # Mazda
    "мазда": "mazda",
    "mazda": "mazda",
    # Ford
    "форд": "ford",
    "ford": "ford",
    # Chevrolet
    "шевроле": "chevrolet",
    "шеви": "chevrolet",
    "chevrolet": "chevrolet",
    # Lada / ВАЗ
    "лада": ["ваз", "lada", "vaz"],
    "lada": ["lada", "ваз", "vaz"],
    "ваз": ["ваз", "lada", "vaz"],
    "жигули": ["ваз", "lada", "vaz"],
    "жигуль": ["ваз", "lada", "vaz"],
    "zhiguli": ["ваз", "lada", "vaz"],
    # ЗАЗ
    "заз": ["заз", "zaz"],
    "запорожец": ["заз", "zaz"],
    "zaporozhets": ["заз", "zaz"],
    # Renault
    "рено": "renault",
    "renault": "renault",
    # Skoda
    "шкода": "skoda",
    "шкодка": "skoda",
    "skoda": "skoda",
    # Mitsubishi
    "митсубиси": "mitsubishi",
    "мицубиси": "mitsubishi",
    "митсу": "mitsubishi",
    "мицу": "mitsubishi",
    "mitsubishi": "mitsubishi",
    # Subaru
    "субару": "subaru",
    "subaru": "subaru",
    # Volvo
    "вольво": "volvo",
    "volvo": "volvo",
    # Porsche
    "порше": "porsche",
    "porsche": "porsche",
    # Land Rover / Range Rover
    "ленд": "land rover",
    "landrover": "land rover",
    "land rover": "land rover",
    "ренджровер": ["land rover", "range rover"],
    "rangerover": ["land rover", "range rover"],
    "range rover": ["land rover", "range rover"],
    # Jeep
    "джип": "jeep",
    "jeep": "jeep",
    # Peugeot
    "пежо": "peugeot",
    "пеж": "peugeot",
    "peugeot": "peugeot",
    # Citroen
    "ситроен": "citroen",
    "citroen": "citroen",
    # Opel
    "опель": "opel",
    "opel": "opel",
    # Fiat
    "фиат": "fiat",
    "fiat": "fiat",
    # Alfa Romeo
    "альфа": "alfa romeo",
    "альфаромео": "alfa romeo",
    "alfa": "alfa romeo",
    "alfaromeo": "alfa romeo",
    # Seat
    "сеат": "seat",
    "seat": "seat",
    # Cupra
    "купра": "cupra",
    "cupra": "cupra",
    # Dacia
    "дачия": "dacia",
    "dacia": "dacia",
    # Mini
    "мини": "mini",
    "mini": "mini",
    # Jaguar
    "ягуар": "jaguar",
    "jaguar": "jaguar",
    # Bentley
    "бентли": "bentley",
    "bentley": "bentley",
    # Rolls-Royce
    "роллс": "rolls-royce",
    "rolls": "rolls-royce",
    "rollsroyce": "rolls-royce",
    # Lamborghini
    "ламборгини": "lamborghini",
    "lamborghini": "lamborghini",
    # Ferrari
    "феррари": "ferrari",
    "ferrari": "ferrari",
    # Maserati
    "мазерати": "maserati",
    "maserati": "maserati",
    # Aston Martin
    "астон": "aston martin",
    "astonmartin": "aston martin",
    # Smart
    "смарт": "smart",
    "smart": "smart",
    # Iveco
    "ивеко": "iveco",
    "iveco": "iveco",
    # Suzuki
    "сузуки": "suzuki",
    "suzuki": "suzuki",
    # Infiniti
    "инфинити": "infiniti",
    "infinity": "infiniti",
    "infiniti": "infiniti",
    # Acura
    "акура": "acura",
    "acura": "acura",
    # Daihatsu
    "дайхатсу": "daihatsu",
    "daihatsu": "daihatsu",
    # Isuzu
    "исузу": "isuzu",
    "isuzu": "isuzu",
    # Genesis
    "генезис": "genesis",
    "genesis": "genesis",
    # SsangYong
    "ссангйонг": "ssangyong",
    "ссанг": "ssangyong",
    "ssangyong": "ssangyong",
    # Daewoo
    "дэу": "daewoo",
    "дайво": "daewoo",
    "daewoo": "daewoo",
    # Dodge
    "додж": "dodge",
    "dodge": "dodge",
    # Chrysler
    "крайслер": "chrysler",
    "chrysler": "chrysler",
    # Cadillac
    "кадиллак": "cadillac",
    "cadillac": "cadillac",
    # Lincoln
    "линкольн": "lincoln",
    "lincoln": "lincoln",
    # Buick
    "буик": "buick",
    "buick": "buick",
    # Hummer
    "хаммер": "hummer",
    "hummer": "hummer",
    # Chery
    "чери": "chery",
    "chery": "chery",
    # Haval
    "хавал": "haval",
    "haval": "haval",
    # Geely
    "джили": "geely",
    "geely": "geely",
    # Tesla
    "тесла": "tesla",
    "tesla": "tesla",
    # LiXiang / Li Auto
    "li": ["lixiang", "li auto", "liauto"],
    "ли": ["lixiang", "li auto", "liauto"],
    "lixiang": ["lixiang", "li auto", "liauto"],
    "лисян": ["lixiang", "li auto"],
    "liauto": ["li auto", "lixiang", "liauto"],
    "лиавто": ["li auto", "lixiang", "liauto"],
    "li auto": ["li auto", "lixiang", "liauto"],
    # Chinese / popular in RU
    "exeed": "exeed",
    "иксид": "exeed",
    "omoda": "omoda",
    "омода": "omoda",
    "tank": "tank",
    "танк": "tank",
    "zeekr": "zeekr",
    "зикр": "zeekr",
    "byd": "byd",
    "бид": "byd",
    "changan": "changan",
    "чанган": "changan",
    "jetour": "jetour",
    "джетур": "jetour",
    "грейтволл": "great wall",
    "greatwall": "great wall",
    "донфенг": "dongfeng",
    "дунфэн": "dongfeng",
    "dongfeng": "dongfeng",
    "фав": "faw",
    "faw": "faw",
    "лифан": "lifan",
    "lifan": "lifan",
    "джак": "jac",
    "jac": "jac",
    "хончи": "hongqi",
    "hongqi": "hongqi",
    "воя": "voyah",
    "voyah": "voyah",
    "айто": "aito",
    "aito": "aito",
    "серс": "seres",
    "seres": "seres",
    "нио": "nio",
    "nio": "nio",
    "икспенг": "xpeng",
    "xpeng": "xpeng",
    "белджи": "belgee",
    "belgee": "belgee",
    "гак": "gac",
    "gac": "gac",
    "бэйджи": "baic",
    "baic": "baic",
    "фортинг": "forthing",
    "forthing": "forthing",
    "венуция": "venucia",
    "venucia": "venucia",
    "свон": "swm",
    "swm": "swm",
    "каи": "kaiyi",
    "kaiyi": "kaiyi",
    "рокс": "rox",
    "rox": "rox",
    "дипл": "deepal",
    "deepal": "deepal",
    "аватар": "avatr",
    "avatr": "avatr",
    # RU / CIS
    "moskvich": ["moskvich", "москвич"],
    "москвич": ["москвич", "moskvich"],
    "uaz": ["уаз", "uaz"],
    "уаз": ["уаз", "uaz"],
    "gaz": ["газ", "gaz"],
    "газ": ["газ", "gaz"],
    "богдан": "bogdan",
    "bogdan": "bogdan",
    "тагаз": "tagaz",
    "tagaz": "tagaz",
    "иж": ["izh", "иж"],
    "ижмаш": ["izh", "иж"],
}

# Короткие токены (<=3) — только явный алиас, без «размытого» поиска.
_SHORT_TOKEN_MAX_LEN = 3


def _normalize_token(token: str) -> str:
    s = token.strip().lower().replace("ё", "е")
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[\s\-_]+", "", s)
    return s


def _norm_name(name: str) -> str:
    return _normalize_token(name)


def _as_hints(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        return value
    return [value]


def _match_hint_in_catalog(hint: str, pass24_models: dict[str, int]) -> str | None:
    h = _normalize_token(hint)
    if not h:
        return None

    indexed = [(_norm_name(name), name) for name in pass24_models]

    # 1. Точное совпадение
    for norm, orig in indexed:
        if norm == h:
            return orig

    # 2. Имя в справочнике начинается с подсказки (lixiang → LiXiang)
    starts = [(norm, orig) for norm, orig in indexed if norm.startswith(h)]
    if len(starts) == 1:
        return starts[0][1]
    if len(starts) > 1:
        starts.sort(key=lambda x: len(x[0]))
        return starts[0][1]

    # 3. Подсказка содержится в имени (ваз → ВАЗ/Lada)
    contains = [(norm, orig) for norm, orig in indexed if h in norm]
    if len(contains) == 1:
        return contains[0][1]
    if len(contains) > 1:
        contains.sort(key=lambda x: (len(x[0]), x[0]))
        return contains[0][1]

    return None


def _match_hints(hints: list[str], pass24_models: dict[str, int]) -> str | None:
    for hint in hints:
        found = _match_hint_in_catalog(hint, pass24_models)
        if found:
            return found
    return None


def _fuzzy_match(token: str, pass24_models: dict[str, int]) -> str | None:
    if len(token) < 4:
        return None

    indexed = [(_norm_name(name), name) for name in pass24_models]

    if token in {n for n, _ in indexed}:
        return next(orig for n, orig in indexed if n == token)

    prefix = [(n, o) for n, o in indexed if n.startswith(token)]
    if len(prefix) == 1:
        return prefix[0][1]

    contains = [(n, o) for n, o in indexed if token in n]
    if len(contains) == 1:
        return contains[0][1]

    return None


def resolve_brand(token: str, pass24_models: dict[str, int]) -> str | None:
    """Определить каноническое имя марки по токену пользователя."""
    key = _normalize_token(token)
    if not key:
        return None

    # Явные алиасы (в т.ч. короткие: li, vw, mb)
    if key in BRAND_ALIASES:
        found = _match_hints(_as_hints(BRAND_ALIASES[key]), pass24_models)
        if found:
            return found

    # Точное имя из справочника
    for name in pass24_models:
        if _norm_name(name) == key:
            return name

    # Нечёткий поиск только для длинных токенов
    if len(key) > _SHORT_TOKEN_MAX_LEN:
        fuzzy = _fuzzy_match(key, pass24_models)
        if fuzzy:
            return fuzzy

        # Частичное совпадение с алиасами (mercedes → mercedes-benz)
        for alias, hints in BRAND_ALIASES.items():
            if len(alias) < 4:
                continue
            if key.startswith(alias) or alias.startswith(key):
                found = _match_hints(_as_hints(hints), pass24_models)
                if found:
                    return found

    return None


def suggest_brands(token: str, pass24_models: dict[str, int], limit: int = 5) -> list[str]:
    """Подсказки «возможно вы имели в виду» при ошибке."""
    key = _normalize_token(token)
    if not key:
        return []

    if key in BRAND_ALIASES:
        found = _match_hints(_as_hints(BRAND_ALIASES[key]), pass24_models)
        if found:
            return [found]

    scored: list[tuple[int, str]] = []
    for name in pass24_models:
        norm = _norm_name(name)
        if key in norm:
            scored.append((len(norm), name))
        elif len(key) >= 4 and norm.startswith(key):
            scored.append((len(norm) + 10, name))

    scored.sort(key=lambda x: x[0])
    return [name for _, name in scored[:limit]]
