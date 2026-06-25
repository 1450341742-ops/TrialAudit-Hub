from datetime import date

import pandas as pd

from app.data import (
    WorkbookBundle,
    data_quality,
    extract_monthly_targets,
    normalize_phase,
    parse_chinese_date_range,
    parse_count,
    split_people,
)


def test_normalize_phase():
    assert normalize_phase("Ⅱ 期") == "II期"
    assert normalize_phase("Ⅲ期") == "III期"


def test_parse_count():
    assert parse_count("12例") == 12
    assert parse_count("3.5天") == 3.5


def test_parse_chinese_date_range():
    start, end = parse_chinese_date_range("1月6日-8日", 2026)
    assert start == date(2026, 1, 6)
    assert end == date(2026, 1, 8)


def test_split_people_removes_duplicates():
    assert split_people("张艳、侯思佳，张艳") == ["张艳", "侯思佳"]


def test_extract_monthly_targets():
    raw = pd.DataFrame([
        ["一月", "第1周", "第2周", "第3周", "第4周", "总院次"],
        ["计划院次", 5, 5, 5, 5, 20],
        ["实际院次", 6, 5, 8, 4, 23],
        ["达成率", 1.2, 1, 1.6, .8, 1.15],
    ])
    bundle = WorkbookBundle({"1、项目总体汇报": raw}, "test.xlsx")
    result = extract_monthly_targets(bundle, 2026, 300)
    assert result.to_dict("records") == [{"年度": 2026, "月份": 1, "计划院次": 20.0, "实际院次": 23.0, "年度目标": 300}]


def test_data_quality_returns_rows():
    projects = pd.DataFrame({"项目编号": ["A", "A"], "中心名称": ["X", "Y"]})
    result = data_quality(projects, pd.DataFrame())
    assert not result.empty
