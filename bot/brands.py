"""Сокращения и синонимы марок → каноническое имя в справочнике PASS24."""

BRAND_ALIASES: dict[str, str] = {
    # Mercedes-Benz
    "мерс": "Mercedes-Benz",
    "мерседес": "Mercedes-Benz",
    "мерин": "Mercedes-Benz",
    "mb": "Mercedes-Benz",
    "benz": "Mercedes-Benz",
    # BMW
    "бмв": "BMW",
    "bmw": "BMW",
    # Audi
    "ауди": "Audi",
    "audi": "Audi",
    # Toyota
    "тойота": "Toyota",
    "toyota": "Toyota",
    # Lexus
    "лексус": "Lexus",
    "lexus": "Lexus",
    # Volkswagen
    "фолькс": "Volkswagen",
    "фольксваген": "Volkswagen",
    "vw": "Volkswagen",
    "volkswagen": "Volkswagen",
    # Hyundai
    "хендай": "Hyundai",
    "хёндай": "Hyundai",
    "хундай": "Hyundai",
    "hyundai": "Hyundai",
    # Kia
    "киа": "Kia",
    "kia": "Kia",
    # Nissan
    "ниссан": "Nissan",
    "nissan": "Nissan",
    # Honda
    "хонда": "Honda",
    "honda": "Honda",
    # Mazda
    "мазда": "Mazda",
    "mazda": "Mazda",
    # Ford
    "форд": "Ford",
    "ford": "Ford",
    # Chevrolet
    "шевроле": "Chevrolet",
    "шеви": "Chevrolet",
    "chevrolet": "Chevrolet",
    # Lada / ВАЗ
    "лада": "Lada",
    "lada": "Lada",
    "ваз": "Lada",
    # Renault
    "рено": "Renault",
    "renault": "Renault",
    # Skoda
    "шкода": "Skoda",
    "skoda": "Skoda",
    # Mitsubishi
    "митсубиси": "Mitsubishi",
    "mitsubishi": "Mitsubishi",
    # Subaru
    "субару": "Subaru",
    "subaru": "Subaru",
    # Volvo
    "вольво": "Volvo",
    "volvo": "Volvo",
    # Porsche
    "порше": "Porsche",
    "porsche": "Porsche",
    # Land Rover
    "ленд": "Land Rover",
    "landrover": "Land Rover",
    "land rover": "Land Rover",
    # Jeep
    "джип": "Jeep",
    "jeep": "Jeep",
    # Chery
    "чери": "Chery",
    "chery": "Chery",
    # Haval
    "хавал": "Haval",
    "haval": "Haval",
    # Geely
    "джили": "Geely",
    "geely": "Geely",
    # Tesla
    "тесла": "Tesla",
    "tesla": "Tesla",
}


def resolve_brand(token: str, pass24_models: dict[str, int]) -> str | None:
    """Определить каноническое имя марки по токену или полному названию."""
    key = token.strip().lower()
    if not key:
        return None

    if key in BRAND_ALIASES:
        candidate = BRAND_ALIASES[key]
        if candidate in pass24_models:
            return candidate

    # Точное совпадение с справочником (регистронезависимо)
    for name in pass24_models:
        if name.lower() == key:
            return name

    # Частичное совпадение: «мерс» уже в aliases; для «mercedes» и т.п.
    for alias, canonical in BRAND_ALIASES.items():
        if key.startswith(alias) or alias.startswith(key):
            if canonical in pass24_models:
                return canonical

    for name in pass24_models:
        if key in name.lower() or name.lower().startswith(key):
            return name

    return None
