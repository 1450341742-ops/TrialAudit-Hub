from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta
from typing import Iterable

import pandas as pd

MONTH_MAP = {
    "一月": 1, "二月": 2, "三月": 3, "四月": 4, "五月": 5, "六月": 6,
    "七月": 7, "八月": 8, "九月": 9, "十月": 10, "十一月": 11, "十二月": 12,
}


def is_blank(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return str(value).strip() in {"", "nan", "None", "null"}


def clean_text(value: object) -> str:
    if is_blank(value):
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\u3000", " ")).strip()


def normalize_phase(value: object) -> str:
    text = clean_text(value).upper().replace("阶段", "期")
    if not text:
        return "待确认"
    text = text.replace("Ⅰ", "I").replace("Ⅱ", "II").replace("Ⅲ", "III").replace("Ⅳ", "IV")
    text = re.sub(r"\s+", "", text)
    aliases = {
        "I期": "I期", "IA期": "Ia期", "IB期": "Ib期", "I/IIA期": "I/IIa期",
        "I/II期": "I/II期", "II期": "II期", "IIA期": "IIa期", "IIB期": "IIb期",
        "II/III期": "II/III期", "II-III期": "II/III期", "III期": "III期", "IV期": "IV期",
    }
    return aliases.get(text, clean_text(value))


def normalize_person(value: object) -> str:
    text = clean_text(value)
    return {"协和老师": "协和", "协和 老师": "协和"}.get(text, text)


def split_people(value: object) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    people: list[str] = []
    for item in re.split(r"[、,，;；/\n]+", text):
        name = normalize_person(item)
        if name and name not in people:
            people.append(name)
    return people


def numeric_value(value: object, default: float = 0.0) -> float:
    if is_blank(value):
        return default
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    match = re.search(r"-?\d+(?:\.\d+)?", clean_text(value).replace(",", ""))
    return float(match.group()) if match else default


def excel_serial_to_datetime(value: float) -> datetime:
    return datetime(1899, 12, 30) + timedelta(days=float(value))


def parse_single_date(value: object, default_year: int = 2026) -> pd.Timestamp | pd.NaT:
    if is_blank(value):
        return pd.NaT
    if isinstance(value, pd.Timestamp):
        return value.normalize()
    if isinstance(value, datetime):
        return pd.Timestamp(value.date())
    if isinstance(value, date):
        return pd.Timestamp(value)
    if isinstance(value, (int, float)) and 20000 <= float(value) <= 80000:
        return pd.Timestamp(excel_serial_to_datetime(float(value)).date())
    text = clean_text(value).replace("年", "-").replace("月", "-").replace("日", "")
    text = re.sub(r"-+", "-", text.replace(".", "-").replace("/", "-")).strip("-")
    parts = [part for part in text.split("-") if part]
    try:
        if len(parts) == 3:
            return pd.Timestamp(datetime(int(parts[0]), int(parts[1]), int(parts[2])))
        if len(parts) == 2:
            return pd.Timestamp(datetime(default_year, int(parts[0]), int(parts[1])))
    except (ValueError, TypeError):
        return pd.NaT
    return pd.NaT


def parse_date_range(value: object, default_year: int = 2026) -> tuple[pd.Timestamp | pd.NaT, pd.Timestamp | pd.NaT]:
    if is_blank(value):
        return pd.NaT, pd.NaT
    if isinstance(value, (pd.Timestamp, datetime, date, int, float)):
        parsed = parse_single_date(value, default_year)
        return parsed, parsed
    text = clean_text(value).replace("至", "-").replace("—", "-").replace("–", "-").replace("~", "-")
    explicit_year = re.search(r"(20\d{2})年", text)
    year = int(explicit_year.group(1)) if explicit_year else default_year
    match = re.search(r"(?:(20\d{2})年)?(\d{1,2})月(\d{1,2})日?\s*-\s*(?:(\d{1,2})月)?(\d{1,2})日?", text)
    if match:
        year = int(match.group(1)) if match.group(1) else year
        start_month, start_day = int(match.group(2)), int(match.group(3))
        end_month = int(match.group(4)) if match.group(4) else start_month
        end_day = int(match.group(5))
        end_year = year + 1 if end_month < start_month else year
        try:
            return pd.Timestamp(datetime(year, start_month, start_day)), pd.Timestamp(datetime(end_year, end_month, end_day))
        except ValueError:
            return pd.NaT, pd.NaT
    match = re.search(r"(\d{1,2})[./-](\d{1,2})\s*-\s*(\d{1,2})[./-](\d{1,2})", text)
    if match:
        start_month, start_day, end_month, end_day = map(int, match.groups())
        end_year = year + 1 if end_month < start_month else year
        try:
            return pd.Timestamp(datetime(year, start_month, start_day)), pd.Timestamp(datetime(end_year, end_month, end_day))
        except ValueError:
            return pd.NaT, pd.NaT
    parsed = parse_single_date(text, year)
    return parsed, parsed


def date_span(start: pd.Timestamp | pd.NaT, end: pd.Timestamp | pd.NaT) -> list[pd.Timestamp]:
    if pd.isna(start) or pd.isna(end) or end < start:
        return []
    return list(pd.date_range(start, end, freq="D"))


def mask_phone(text: object) -> str:
    return re.sub(r"(?<!\d)(1\d{2})\d{4}(\d{4})(?!\d)", r"\1****\2", clean_text(text))


def month_label(month: int) -> str:
    return f"{int(month)}月"


def unique_nonblank(values: Iterable[object]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = clean_text(value)
        if text and text not in result:
            result.append(text)
    return result
