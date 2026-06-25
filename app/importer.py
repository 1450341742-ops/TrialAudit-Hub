from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Any

import pandas as pd

from app.data import (
    WorkbookBundle,
    extract_flow,
    extract_monthly_targets,
    extract_parttime,
    extract_projects,
    extract_schedule,
    normalize_phase,
    parse_count,
    parse_date_value,
    parse_chinese_date_range,
    split_people,
)
from app.db import SupabaseRepository


def _text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text if text and text.lower() != "nan" else None


def _number(value: Any, default: float | None = None) -> float | None:
    parsed = parse_count(value)
    return default if pd.isna(parsed) else float(parsed)


def _date(value: Any, year: int = 2026) -> date | None:
    return parse_date_value(value, year)


def _bool_from_status(value: Any) -> bool:
    text = str(value or "")
    return any(token in text for token in ["定稿", "完成", "结束", "是"])



STANDARD_STATUSES = {"待确认", "待排班", "已排班", "稽查中", "待报告", "待CAPA", "已完成", "已取消", "历史导入"}


def _derive_status(row: pd.Series, source_year: int = 2026) -> str:
    raw_status = _text(row.get("项目状态"))
    report_status = _text(row.get("报告跟踪情况")) or _text(row.get("报告预计回复报告时间"))
    capa_status = _text(row.get("CAPA跟踪情况")) or _text(row.get("CAPA预计回复报告时间"))
    finalized = _bool_from_status(row.get("定稿状态")) or _bool_from_status(row.get("报告定稿"))
    if finalized or any(token in str(capa_status or "") for token in ["结束", "定稿", "完成"]):
        return "已完成"
    if capa_status:
        return "待CAPA"
    if report_status:
        return "待报告"
    _, audit_end = parse_chinese_date_range(row.get("稽查时间"), year_hint=source_year)
    if audit_end:
        return "待报告"
    if raw_status in STANDARD_STATUSES:
        return raw_status
    return "历史导入"


def _stable_key(*parts: Any) -> str:
    joined = "|".join(str(part or "").strip() for part in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()


def projects_to_records(projects: pd.DataFrame, source_year: int = 2026) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for _, row in projects.iterrows():
        project_code = _text(row.get("项目编号"))
        if not project_code:
            continue
        records.append({
            "project_code": project_code,
            "sponsor_project_code": _text(row.get("申办方项目编号")),
            "center_name": _text(row.get("中心名称")),
            "sponsor_type": _text(row.get("申办方类型")) or "未分类",
            "center_type": _text(row.get("中心类型")) or "未分类",
            "phase": normalize_phase(row.get("分期")),
            "therapeutic_area": _text(row.get("疾病领域")),
            "visit_count": _number(row.get("院次数"), 1),
            "case_count": int(_number(row.get("病例数"), 0) or 0),
            "status": "历史导入",
            "source_year": source_year,
        })
    return records


def flow_projects_to_records(flow: pd.DataFrame, source_year: int = 2026) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for _, row in flow.iterrows():
        project_code = _text(row.get("项目编号"))
        if not project_code:
            continue
        records.append({
            "project_code": project_code,
            "sponsor_project_code": _text(row.get("申办方项目编号")),
            "center_name": _text(row.get("中心名称")),
            "sponsor_type": _text(row.get("申办方")) or _text(row.get("申办方类型")) or "未分类",
            "center_type": "未分类",
            "phase": normalize_phase(row.get("分期")),
            "therapeutic_area": _text(row.get("疾病领域")),
            "visit_count": _number(row.get("院次数"), 1),
            "case_count": int(_number(row.get("病例数"), 0) or 0),
            "status": _derive_status(row, source_year),
            "source_year": source_year,
        })
    return records


def flows_to_records(flow: pd.DataFrame, project_ids: dict[str, str], source_year: int = 2026) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for _, row in flow.iterrows():
        project_code = _text(row.get("项目编号"))
        project_id = project_ids.get(project_code or "")
        if not project_code or not project_id:
            continue
        start, end = parse_chinese_date_range(row.get("稽查时间"), year_hint=source_year)
        report_due = _date(row.get("报告预计回复报告时间"), source_year)
        capa_due = _date(row.get("CAPA预计回复报告时间"), source_year)
        records.append({
            "project_id": project_id,
            "project_code": project_code,
            "lead_auditor": _text(row.get("组长")),
            "auditors": split_people(row.get("参与稽查员")),
            "audit_time_text": _text(row.get("稽查时间")),
            "audit_start_date": start,
            "audit_end_date": end,
            "startup_letter_date": _date(row.get("启动函"), source_year),
            "cra_contact": _text(row.get("CRA联系方式")),
            "materials_status": _text(row.get("资料状态")),
            "dingpan_status": _text(row.get("钉盘状态")),
            "edc_status": _text(row.get("EDC状态")),
            "finance_status": _text(row.get("有成财务")),
            "business_info_status": _text(row.get("商务信息表上传")),
            "qualification_status": _text(row.get("资质寄送情况")) or _text(row.get("资质要求")),
            "confirmation_letter_date": _date(row.get("确认函"), source_year),
            "thank_you_letter_date": _date(row.get("感谢信"), source_year),
            "report_due_date": report_due,
            "report_status": _text(row.get("报告跟踪情况")) or _text(row.get("报告预计回复报告时间")),
            "capa_due_date": capa_due,
            "capa_status": _text(row.get("CAPA跟踪情况")) or _text(row.get("CAPA预计回复报告时间")),
            "status": _derive_status(row, source_year),
            "express_no": _text(row.get("快递单号")),
            "finalized": _bool_from_status(row.get("定稿状态")) or _bool_from_status(row.get("报告定稿")),
            "collection_count": int(_number(row.get("回款次数"), 0) or 0),
            "contract_amount": _number(row.get("合同金额"), 0),
            "received_amount": _number(row.get("实际回款金额"), 0),
            "ding_upload_status": _text(row.get("钉钉信息状态")),
            "notes": _text(row.get("钉钉备注")) or _text(row.get("备注")) or (_text(row.get("项目状态")) if _text(row.get("项目状态")) not in STANDARD_STATUSES else None),
        })
    return records


def schedules_to_records(schedule: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for _, row in schedule.iterrows():
        name = _text(row.get("稽查员"))
        work_date = row.get("工作日期")
        if not name or not work_date:
            continue
        records.append({
            "source_key": _stable_key(name, work_date, "excel"),
            "auditor_name": name,
            "work_date": work_date,
            "availability_status": _text(row.get("状态")) or "占用",
            "notes": "Excel导入",
        })
    return records


def parttime_to_records(parttime: pd.DataFrame, year: int = 2026) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for idx, row in parttime.iterrows():
        name = _text(row.get("姓名"))
        if not name:
            continue
        month = int(row.get("月份数字")) if pd.notna(row.get("月份数字")) else 1
        start = row.get("开始日期")
        end = row.get("结束日期")
        records.append({
            "source_key": _stable_key(name, start or f"{year}-{month}", row.get("项目时间"), idx),
            "auditor_name": name,
            "period_month": date(year, month, 1),
            "work_start_date": start,
            "work_end_date": end,
            "work_days": _number(row.get("天数"), 0),
            "payment_status": "待确认",
            "notes": _text(row.get("项目时间")) or "Excel导入",
        })
    return records


def targets_to_records(targets: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for _, row in targets.iterrows():
        records.append({
            "year": int(row.get("年度")),
            "month": int(row.get("月份")),
            "planned_visits": _number(row.get("计划院次"), 0),
            "actual_visits": _number(row.get("实际院次"), 0),
            "annual_target": _number(row.get("年度目标"), 300),
            "notes": "Excel导入",
        })
    return records


def auditor_records(flow: pd.DataFrame, schedule: pd.DataFrame, parttime: pd.DataFrame) -> list[dict[str, Any]]:
    names: dict[str, str] = {}
    if not flow.empty:
        for value in flow.get("参与稽查员", pd.Series(dtype=object)):
            for name in split_people(value):
                names[name] = "正式"
        for value in flow.get("组长", pd.Series(dtype=object)):
            name = _text(value)
            if name:
                names[name] = "正式"
    if not schedule.empty:
        for name in schedule.get("稽查员", pd.Series(dtype=object)).dropna().astype(str):
            names[name.strip()] = "正式"
    if not parttime.empty:
        for name in parttime.get("姓名", pd.Series(dtype=object)).dropna().astype(str):
            names.setdefault(name.strip(), "兼职")
    return [{"name": name, "employment_type": employment_type, "active": True} for name, employment_type in sorted(names.items()) if name]


def import_workbooks(
    repo: SupabaseRepository,
    weekly_bundle: WorkbookBundle | None,
    flow_bundle: WorkbookBundle | None,
    *,
    year: int = 2026,
    annual_target: int = 300,
) -> dict[str, int]:
    projects = extract_projects(weekly_bundle) if weekly_bundle else pd.DataFrame()
    schedule = extract_schedule(weekly_bundle, year=year) if weekly_bundle else pd.DataFrame()
    parttime = extract_parttime(weekly_bundle, year=year) if weekly_bundle else pd.DataFrame()
    targets = extract_monthly_targets(weekly_bundle, year=year, annual_target=annual_target) if weekly_bundle else pd.DataFrame()
    flow = extract_flow(flow_bundle or weekly_bundle, preferred_year=year) if (flow_bundle or weekly_bundle) else pd.DataFrame()

    project_records = projects_to_records(projects, year)
    flow_project_records = flow_projects_to_records(flow, year)
    merged_projects = {record["project_code"]: record for record in flow_project_records}
    for record in project_records:
        existing = merged_projects.get(record["project_code"], {})
        merged = {**existing, **record}
        if existing.get("status"):
            merged["status"] = existing["status"]
        merged_projects[record["project_code"]] = merged

    counts: dict[str, int] = {}
    counts["projects"] = repo.upsert_many("projects", merged_projects.values(), on_conflict="project_code")
    project_rows = repo.fetch("projects", "id,project_code", limit=10000)
    project_ids = {row["project_code"]: row["id"] for row in project_rows}

    counts["auditors"] = repo.upsert_many("auditors", auditor_records(flow, schedule, parttime), on_conflict="name")
    counts["project_flows"] = repo.upsert_many("project_flows", flows_to_records(flow, project_ids, year), on_conflict="project_id")
    counts["schedules"] = repo.upsert_many("schedules", schedules_to_records(schedule), on_conflict="source_key")
    counts["parttime_entries"] = repo.upsert_many("parttime_entries", parttime_to_records(parttime, year), on_conflict="source_key")
    counts["monthly_targets"] = repo.upsert_many("monthly_targets", targets_to_records(targets), on_conflict="year,month")
    return counts
