import pandas as pd

from trialaudit_hub.services.quality import build_quality_report


def test_quality_report_flags_duplicate_and_invalid_date():
    projects = pd.DataFrame(
        {
            "project_no": ["P-1", "P-1"],
            "site_name": ["中心A", "中心A"],
            "audit_period": ["1月3日-2日", "1月3日-2日"],
            "audit_start": pd.to_datetime(["2026-01-03", "2026-01-03"]),
            "audit_end": pd.to_datetime(["2026-01-02", "2026-01-02"]),
            "phase": ["III期", "III期"],
        }
    )
    report = build_quality_report(projects, pd.DataFrame(), pd.DataFrame())
    assert "重复项目" in report["category"].tolist()
    assert "日期" in report["category"].tolist()
