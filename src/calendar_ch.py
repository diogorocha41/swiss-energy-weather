"""Swiss public holidays (national + widely observed) used as a calendar feature.

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


def holiday_frame(start_year: int, end_year: int) -> pd.DataFrame:
    rows = [
        {"holiday_date": d, "holiday_name": n}
        for y in range(start_year, end_year + 1)
        for d, n in swiss_holidays(y)
    ]
    df = pd.DataFrame(rows)
    df["holiday_date"] = pd.to_datetime(df["holiday_date"])
    return df
