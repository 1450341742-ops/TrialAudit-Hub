from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from .normalization import clean_text, date_span


@dataclass(frozen=True)
class KPISet:
    annual_target: int
    completed: int
    annual_rate: float
    current_month_plan: int
    current_month_actual: int
    current_month_rate: float | None
    ongoing_projects: int
    pending_reports: int
    overdue_reports: int
    pending_capa: int
    high_load_people: int
    parttime_cost: float


def valid_projects(projects: pd.DataFrame) -> pd.DataFrame:
    if projects.empty:
        return projects.copy()
    if "is_valid" in projects.columns:
        return projects[projects["is_valid"]].copy()
    return projects[projects.get("project_no", "").astype(str).str.strip().ne("")].copy()


def monthly_actual(projects: pd.DataFrame, year: int = 2026) -> pd.DataFrame:
    df = valid_projects(projects)
    if df.empty or "audit_end" not in df.columns:
        return pd.DataFrame({"month": range(1, 13), "actual": [0] * 12})
    dates = pd.to_datetime(df["audit_end"], errors="coerce")
    counts = dates[dates.dt.year.eq(year)].dt.month.value_counts().to_dict()
    return pd.DataFrame({"month": range(1, 13), "actual": [int(counts.get(month, 0)) for month in range(1, 13)]})


def monthly_plan_actual(projects: pd.DataFrame, targets: pd.DataFrame, year: int = 2026) -> pd.DataFrame:
    actual = monthly_actual(projects, year)
    base = pd.DataFrame({"month": range(1, 13)})
    if targets.empty:
        base["plan"] = 0
    else:
        plan = targets[["month", "plan"]].drop_duplicates("month", keep="last")
        base = base.merge(plan, on="month", how="left")
        base["plan"] = base["plan"].fillna(0)
    base = base.merge(actual, on="month", how="left")
    base["actual"] = base["actual"].fillna(0).astype(int)
    base["plan"] = base["plan"].fillna(0).astype(int)
    base["achievement_rate"] = base.apply(
        lambda row: row["actual"] / row["plan"] if row["plan"] else None,
        axis=1,
    )
    base["month_label"] = base["month"].map(lambda value: f"{value}月")
    base["cumulative_plan"] = base["plan"].cumsum()
    base["cumulative_actual"] = base["actual"].cumsum()
    return base


def derive_project_status(row: pd.Series, today: date | None = None) -> str:
    today_ts = pd.Timestamp(today or date.today())
    finalized = " ".join(filter(None, [clean_text(row.get("finalized")), clean_text(row.get("status_raw"))]))
    report_tracking = " ".join(
        filter(
            None,
            [clean_text(row.get("report_tracking")), clean_text(row.get("report_due")), clean_text(row.get("status_raw"))],
        )
    )
    capa_tracking = " ".join(
        filter(
            None,
            [clean_text(row.get("capa_tracking")), clean_text(row.get("capa_due")), clean_text(row.get("status_raw"))],
        )
    )
    audit_start = pd.to_datetime(row.get("audit_start"), errors="coerce")
    audit_end = pd.to_datetime(row.get("audit_end"), errors="coerce")
    if finalized and any(token in finalized for token in ["定稿", "完成", "是"]):
        return "已完成"
    if capa_tracking and not any(token in capa_tracking for token in ["结束", "完成", "不适用"]):
        return "待CAPA"
    if report_tracking and not any(token in report_tracking for token in ["定稿", "结束", "完成"]):
        return "待报告"
    if not pd.isna(audit_start) and not pd.isna(audit_end):
        if audit_start <= today_ts <= audit_end:
            return "稽查中"
        if audit_end < today_ts:
            return "待报告"
        return "已排班"
    return "待确认"


def flow_with_status(flows: pd.DataFrame, today: date | None = None) -> pd.DataFrame:
    if flows.empty:
        return flows.copy()
    result = flows.copy()
    result["derived_status"] = result.apply(lambda row: derive_project_status(row, today), axis=1)
    today_ts = pd.Timestamp(today or date.today())
    result["report_overdue_days"] = 0
    if "report_due" in result:
        due = pd.to_datetime(result["report_due"], errors="coerce")
        is_done = result["report_tracking"].map(clean_text).str.contains("定稿|结束|完成", regex=True, na=False)
        result["report_overdue_days"] = (
            ((today_ts - due).dt.days.clip(lower=0)).where(due.notna() & ~is_done, 0).fillna(0).astype(int)
        )
    result["capa_overdue_days"] = 0
    if "capa_due" in result:
        due = pd.to_datetime(result["capa_due"], errors="coerce")
        is_done = result["capa_tracking"].map(clean_text).str.contains("结束|完成|不适用", regex=True, na=False)
        result["capa_overdue_days"] = (
            ((today_ts - due).dt.days.clip(lower=0)).where(due.notna() & ~is_done, 0).fillna(0).astype(int)
        )
    return result


def staff_calendar(projects: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, row in valid_projects(projects).iterrows():
        people = row.get("auditors", []) or []
        dates = date_span(row.get("audit_start"), row.get("audit_end"))
        for person in people:
            for day in dates:
                rows.append(
                    {
                        "person": person,
                        "date": day,
                        "month": int(day.month),
                        "project_no": row.get("project_no", ""),
                        "site_name": row.get("site_name", ""),
                    }
                )
    return pd.DataFrame(rows)


def staff_load(projects: pd.DataFrame) -> pd.DataFrame:
    calendar = staff_calendar(projects)
    columns = [
        "person",
        "month",
        "journey_days",
        "project_count",
        "max_consecutive_days",
        "conflict_days",
        "load_level",
    ]
    if calendar.empty:
        return pd.DataFrame(columns=columns)
    unique_days = calendar.drop_duplicates(["person", "date"])
    project_counts = calendar.groupby(["person", "month"])["project_no"].nunique().rename("project_count")
    journey_days = unique_days.groupby(["person", "month"])["date"].nunique().rename("journey_days")
    conflicts = calendar.groupby(["person", "date"])["project_no"].nunique().gt(1).groupby(level=0).sum()
    consecutive_rows: list[dict[str, object]] = []
    for (person, month), group in unique_days.groupby(["person", "month"]):
        ordered = sorted(pd.to_datetime(group["date"]).dt.date.unique())
        best = current = 0
        previous = None
        for item in ordered:
            current = current + 1 if previous is not None and (item - previous).days == 1 else 1
            best = max(best, current)
            previous = item
        consecutive_rows.append({"person": person, "month": month, "max_consecutive_days": best})
    consecutive = pd.DataFrame(consecutive_rows).set_index(["person", "month"])["max_consecutive_days"]
    result = pd.concat([journey_days, project_counts, consecutive], axis=1).reset_index()
    result["conflict_days"] = result["person"].map(conflicts).fillna(0).astype(int)
    result["load_level"] = result["journey_days"].map(
        lambda value: "高负荷" if value >= 18 else ("关注" if value >= 15 else "正常")
    )
    return result.sort_values(["month", "journey_days"], ascending=[True, False]).reset_index(drop=True)


def node_completion(flows: pd.DataFrame) -> pd.DataFrame:
    if flows.empty:
        return pd.DataFrame(columns=["node", "completed", "total", "completion_rate"])
    valid = flows[flows.get("is_valid", True)].copy()
    specs = {
        "启动函": (["kickoff_letter"], r".+", r"无需|不适用"),
        "资料": (["materials"], r"收到|已|完成", r"无需|不适用"),
        "钉盘": (["ding_space"], r"确认|已|完成", r"无需|不适用"),
        "EDC": (["edc"], r"开通|已|完成", r"无需|不适用"),
        "确认函": (["confirmation_letter"], r".+", r"无需|不适用"),
        "感谢信": (["thank_you_letter"], r".+", r"无需|不适用"),
        "报告": (["report_tracking", "report_due", "status_raw"], r"定稿|结束|完成|全部定稿", r"无需|不适用"),
        "CAPA": (["capa_tracking", "capa_due", "status_raw"], r"结束|完成|定稿|全部定稿", r"无需|不适用"),
        "定稿": (["finalized", "status_raw"], r"定稿|完成|是", r"无需|不适用"),
    }
    rows: list[dict[str, object]] = []
    for label, (columns_to_use, done_pattern, not_applicable_pattern) in specs.items():
        values = pd.Series("", index=valid.index, dtype=str)
        for column in columns_to_use:
            if column in valid:
                values = values.str.cat(valid[column].map(clean_text), sep=" ").str.strip()
        applicable = ~values.str.contains(not_applicable_pattern, regex=True, na=False)
        completed = values.str.contains(done_pattern, regex=True, na=False)
        total = int(applicable.sum())
        done = int((completed & applicable).sum())
        rows.append({"node": label, "completed": done, "total": total, "completion_rate": done / total if total else None})
    return pd.DataFrame(rows)


def calculate_kpis(
    projects: pd.DataFrame,
    flows: pd.DataFrame,
    targets: pd.DataFrame,
    parttime: pd.DataFrame,
    annual_target: int = 300,
    year: int = 2026,
    month: int | None = None,
    today: date | None = None,
) -> KPISet:
    month = month or (today or date.today()).month
    monthly = monthly_plan_actual(projects, targets, year)
    current = monthly.loc[monthly["month"].eq(month)]
    current_plan = int(current["plan"].iloc[0]) if not current.empty else 0
    current_actual = int(current["actual"].iloc[0]) if not current.empty else 0
    completed = int(monthly["actual"].sum())
    flow_status = flow_with_status(flows, today)
    status_counts = flow_status.get("derived_status", pd.Series(dtype=str)).value_counts()
    load = staff_load(projects)
    parttime_cost = (
        float(parttime.loc[parttime.get("month", pd.Series(dtype=float)).eq(month), "amount"].sum())
        if not parttime.empty
        else 0.0
    )
    return KPISet(
        annual_target=annual_target,
        completed=completed,
        annual_rate=completed / annual_target if annual_target else 0,
        current_month_plan=current_plan,
        current_month_actual=current_actual,
        current_month_rate=current_actual / current_plan if current_plan else None,
        ongoing_projects=int(status_counts.get("已排班", 0) + status_counts.get("稽查中", 0)),
        pending_reports=int(status_counts.get("待报告", 0)),
        overdue_reports=int((flow_status.get("report_overdue_days", pd.Series(dtype=int)) > 0).sum()),
        pending_capa=int(status_counts.get("待CAPA", 0)),
        high_load_people=(
            int((load.loc[load["month"].eq(month), "load_level"] == "高负荷").sum()) if not load.empty else 0
        ),
        parttime_cost=parttime_cost,
    )
