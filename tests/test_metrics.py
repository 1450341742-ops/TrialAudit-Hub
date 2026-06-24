import pandas as pd

from trialaudit_hub.services.metrics import monthly_plan_actual, staff_load


def test_monthly_actual_uses_audit_end_month():
    projects = pd.DataFrame(
        {
            "project_no": ["A", "B", "C"],
            "site_name": ["S1", "S2", "S3"],
            "audit_end": pd.to_datetime(["2026-01-03", "2026-01-20", "2026-02-01"]),
            "is_valid": [True, True, True],
        }
    )
    targets = pd.DataFrame({"month": [1, 2], "plan": [3, 4]})
    result = monthly_plan_actual(projects, targets, 2026)
    assert result.loc[result["month"] == 1, "actual"].iloc[0] == 2
    assert result.loc[result["month"] == 2, "actual"].iloc[0] == 1


def test_staff_load_deduplicates_overlapping_days_and_flags_conflict():
    projects = pd.DataFrame(
        {
            "project_no": ["A", "B"],
            "site_name": ["S1", "S2"],
            "audit_start": pd.to_datetime(["2026-01-01", "2026-01-02"]),
            "audit_end": pd.to_datetime(["2026-01-03", "2026-01-04"]),
            "auditors": [["张三"], ["张三"]],
            "is_valid": [True, True],
        }
    )
    result = staff_load(projects)
    row = result.iloc[0]
    assert row["journey_days"] == 4
    assert row["conflict_days"] == 2
    assert row["max_consecutive_days"] == 4
