import pandas as pd

from app.data import data_quality, normalize_phase, parse_count


def test_normalize_phase():
    assert normalize_phase("Ⅱ 期") == "II期"
    assert normalize_phase("Ⅲ期") == "III期"


def test_parse_count():
    assert parse_count("12例") == 12
    assert parse_count("3.5天") == 3.5


def test_data_quality_returns_rows():
    projects = pd.DataFrame({"项目编号": ["A", "A"], "中心名称": ["X", "Y"]})
    result = data_quality(projects, pd.DataFrame())
    assert not result.empty
