"""Преобразование произнесённых цифр в числа для голосового ввода."""

import re

# Отдельные цифры: «шесть пять шесть» → 656
_DIGIT_WORDS: dict[str, str] = {
    "ноль": "0",
    "нуля": "0",
    "нолик": "0",
    "один": "1",
    "одна": "1",
    "одну": "1",
    "раз": "1",
    "два": "2",
    "две": "2",
    "три": "3",
    "четыре": "4",
    "четырёх": "4",
    "четырех": "4",
    "пять": "5",
    "пяти": "5",
    "шесть": "6",
    "шести": "6",
    "семь": "7",
    "семи": "7",
    "восемь": "8",
    "восьми": "8",
    "девять": "9",
    "девяти": "9",
}

# Составные числа до 999: «сто двадцать один» → 121
_TENS: dict[str, int] = {
    "двадцать": 20,
    "тридцать": 30,
    "сорок": 40,
    "пятьдесят": 50,
    "шестьдесят": 60,
    "семьдесят": 70,
    "восемьдесят": 80,
    "девяносто": 90,
}
_HUNDREDS: dict[str, int] = {
    "сто": 100,
    "двести": 200,
    "триста": 300,
    "четыреста": 400,
    "пятьсот": 500,
    "шестьсот": 600,
    "семьсот": 700,
    "восемьсот": 800,
    "девятьсот": 900,
}
_TEENS: dict[str, int] = {
    "десять": 10,
    "одиннадцать": 11,
    "двенадцать": 12,
    "тринадцать": 13,
    "четырнадцать": 14,
    "пятнадцать": 15,
    "шестнадцать": 16,
    "семнадцать": 17,
    "восемнадцать": 18,
    "девятнадцать": 19,
}
_ONES: dict[str, int] = {
    "один": 1,
    "одна": 1,
    "два": 2,
    "две": 2,
    "три": 3,
    "четыре": 4,
    "пять": 5,
    "шесть": 6,
    "семь": 7,
    "восемь": 8,
    "девять": 9,
}

_TOKEN_RE = re.compile(r"[а-яёa-z0-9]+", re.IGNORECASE)


def _clean_token(token: str) -> str:
    return token.lower().replace("ё", "е")


def _parse_compound_number(tokens: list[str], start: int) -> tuple[int | None, int]:
    """Разобрать составное число с позиции start; вернуть (значение, длина)."""
    if start >= len(tokens):
        return None, 0

    t0 = _clean_token(tokens[start])
    if t0 in _TEENS:
        return _TEENS[t0], 1
    if t0 in _ONES and (start + 1 >= len(tokens) or _clean_token(tokens[start + 1]) not in _TENS):
        # одиночная цифра-слово в составном контексте
        if t0 in _HUNDREDS or t0 in _TENS:
            pass
        elif start + 1 < len(tokens) and _clean_token(tokens[start + 1]) in _TENS:
            pass
        else:
            return _ONES[t0], 1

    total = 0
    i = start
    consumed = 0

    while i < len(tokens):
        t = _clean_token(tokens[i])
        if t in _HUNDREDS:
            total += _HUNDREDS[t]
            consumed += 1
            i += 1
            continue
        if t in _TEENS:
            total += _TEENS[t]
            consumed += 1
            break
        if t in _TENS:
            total += _TENS[t]
            consumed += 1
            i += 1
            if i < len(tokens) and _clean_token(tokens[i]) in _ONES:
                total += _ONES[_clean_token(tokens[i])]
                consumed += 1
            break
        if t in _ONES and total > 0:
            total += _ONES[t]
            consumed += 1
            break
        if t in _ONES and total == 0 and (i + 1 >= len(tokens) or _clean_token(tokens[i + 1]) not in _TENS):
            return _ONES[t], 1
        break

    if consumed == 0:
        return None, 0
    return total, consumed


def normalize_spoken_numbers(text: str) -> str:
    """
    «мазда шесть пять шесть» → «мазда 656»
    «мазда сто двадцать один» → «мазда 121»
    """
    raw_tokens = _TOKEN_RE.findall(text)
    if not raw_tokens:
        return text

    out: list[str] = []
    i = 0
    while i < len(raw_tokens):
        t = _clean_token(raw_tokens[i])

        if t in _DIGIT_WORDS:
            digits: list[str] = []
            while i < len(raw_tokens) and _clean_token(raw_tokens[i]) in _DIGIT_WORDS:
                digits.append(_DIGIT_WORDS[_clean_token(raw_tokens[i])])
                i += 1
            out.append("".join(digits))
            continue

        if t in _HUNDREDS or t in _TEENS or (t in _TENS) or (
            t in _ONES and i + 1 < len(raw_tokens) and _clean_token(raw_tokens[i + 1]) in _TENS
        ):
            value, length = _parse_compound_number(raw_tokens, i)
            if value is not None and length > 0:
                out.append(str(value))
                i += length
                continue

        out.append(raw_tokens[i])
        i += 1

    return " ".join(out)
