"""Public holidays for Switzerland and Portugal, used as a calendar feature.

Electricity demand on holidays looks like a Sunday, so flagging them improves
any consumption model. Cantonal holidays differ; this list keeps the days
observed in most of Switzerland.
"""
from datetime import date, timedelta

import pandas as pd


def easter_sunday(year: int) -> date:
    """Anonymous Gregorian algorithm (Meeus/Jones/Butcher)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def swiss_holidays(year: int) -> list[tuple[date, str]]:
    easter = easter_sunday(year)
    return [
        (date(year, 1, 1), "New Year's Day"),
        (date(year, 1, 2), "Berchtoldstag"),
        (easter - timedelta(days=2), "Good Friday"),
        (easter + timedelta(days=1), "Easter Monday"),
        (easter + timedelta(days=39), "Ascension Day"),
        (easter + timedelta(days=50), "Whit Monday"),
        (date(year, 8, 1), "Swiss National Day"),
        (date(year, 12, 25), "Christmas Day"),
        (date(year, 12, 26), "St Stephen's Day"),
    ]


def portugal_holidays(year: int) -> list[tuple[date, str]]:
    """National public holidays in Portugal (mainland)."""
    easter = easter_sunday(year)
    return [
        (date(year, 1, 1), "Ano Novo"),
        (easter - timedelta(days=2), "Sexta-feira Santa"),
        (easter, "Páscoa"),
        (date(year, 4, 25), "Dia da Liberdade"),
        (date(year, 5, 1), "Dia do Trabalhador"),
        (easter + timedelta(days=60), "Corpo de Deus"),
        (date(year, 6, 10), "Dia de Portugal"),
        (date(year, 8, 15), "Assunção de Nossa Senhora"),
        (date(year, 10, 5), "Implantação da República"),
        (date(year, 11, 1), "Dia de Todos os Santos"),
        (date(year, 12, 1), "Restauração da Independência"),
        (date(year, 12, 8), "Imaculada Conceição"),
        (date(year, 12, 25), "Natal"),
    ]


HOLIDAY_FUNCTIONS = {"CH": swiss_holidays, "PT": portugal_holidays}


def holiday_frame(start_year: int, end_year: int) -> pd.DataFrame:
    rows = [
        {"country": country, "holiday_date": d, "holiday_name": n}
        for country, fn in HOLIDAY_FUNCTIONS.items()
        for y in range(start_year, end_year + 1)
        for d, n in fn(y)
    ]
    df = pd.DataFrame(rows)
    df["holiday_date"] = pd.to_datetime(df["holiday_date"])
    return df
