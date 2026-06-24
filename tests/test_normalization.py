import pandas as pd

from trialaudit_hub.services.normalization import normalize_phase, parse_date_range, split_people


def test_normalize_phase_variants():
    assert normalize_phase("Ⅰ 期") == "I期"
    assert normalize_phase("II-III期") == "II/III期"
    assert normalize_phase("Ⅱb期") == "IIb期"


def test_parse_chinese_date_range():
    start, end = parse_date_range("3月30日-4月3日", 2026)
    assert start == pd.Timestamp("2026-03-30")
    assert end == pd.Timestamp("2026-04-03")


def test_parse_excel_serial_date():
    start, end = parse_date_range(46134, 2026)
    assert start == end
    assert start.year == 2026


def test_split_people_and_aliases():
    assert split_people("张三、协和老师、张三") == ["张三", "协和"]
