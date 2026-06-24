from __future__ import annotations

from datetime import date

import pandas as pd


def to_frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def dashboard_frames(repo):
    projects = to_frame(repo.fetch("projects", order_by="created_at", descending=True))
    flows = to_frame(repo.fetch("project_flows", order_by="updated_at", descending=True))
    schedules = to_frame(repo.fetch("schedules", order_by="work_date", descending=True))
    parttime = to_frame(repo.fetch("parttime_entries", order_by="period_month", descending=True))
    targets = to_frame(repo.fetch("monthly_targets", order_by="month"))
    return projects, flows, schedules, parttime, targets


def overdue_flags(flows: pd.DataFrame) -> pd.DataFrame:
    if flows.empty:
        return flows.copy()
    frame = flows.copy()
    today = pd.Timestamp(date.today())
    frame["report_due_date"] = pd.to_datetime(frame.get("report_due_date"), errors="coerce")
    frame["capa_due_date"] = pd.to_datetime(frame.get("capa_due_date"), errors="coerce")
    frame["报告逾期"] = frame["report_due_date"].notna() & (frame["report_due_date"] < today) & ~frame.get("report_status", pd.Series(index=frame.index, dtype=object)).fillna("").astype(str).str.contains("结束|定稿|完成")
    frame["CAPA逾期"] = frame["capa_due_date"].notna() & (frame["capa_due_date"] < today) & ~frame.get("capa_status", pd.Series(index=frame.index, dtype=object)).fillna("").astype(str).str.contains("结束|定稿|完成")
    return frame


def parttime_amount(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=float)
    work_days = pd.to_numeric(frame.get("work_days", 0), errors="coerce").fillna(0)
    daily_rate = pd.to_numeric(frame.get("daily_rate", 0), errors="coerce").fillna(0)
    adjustment = pd.to_numeric(frame.get("adjustment_amount", 0), errors="coerce").fillna(0)
    return work_days * daily_rate + adjustment
