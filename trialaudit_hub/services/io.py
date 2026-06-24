from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Mapping

import pandas as pd

from .normalization import (
    clean_text,
    mask_phone,
    normalize_phase,
    numeric_value,
    parse_date_range,
    parse_single_date,
    split_people,
)


@dataclass
class DataBundle:
    projects: pd.DataFrame = field(default_factory=pd.DataFrame)
    flows: pd.DataFrame = field(default_factory=pd.DataFrame)
    targets: pd.DataFrame = field(default_factory=pd.DataFrame)
    parttime: pd.DataFrame = field(default_factory=pd.DataFrame)
    journey_calendar: pd.DataFrame = field(default_factory=pd.DataFrame)
    multi_center: pd.DataFrame = field(default_factory=pd.DataFrame)
    raw_sheets: dict[str, pd.DataFrame] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


COLUMN_ALIASES = {
    "项目编号": "project_no",
    "内部项目编号": "project_no",
    "申办方项目编号": "sponsor_project_no",
    "中心名称": "site_name",
    "医院": "site_name",
    "申办方": "sponsor_type",
    "分期": "phase",
    "项目类型": "disease_area",
    "疾病领域": "disease_area",
    "数量": "quantity",
    "参与稽查的老师": "auditors_raw",
    "参与稽查老师": "auditors_raw",
    "组长/撰写人": "lead_auditor",
    "例数": "case_count",
    "例": "case_count",
    "多单中心": "center_mode",
    "稽查时间": "audit_period",
}

FLOW_NODE_COLUMNS = {
    "启动函": "kickoff_letter",
    "CRA联系方式": "cra_contact",
    "资料": "materials",
    "是否创建钉盘": "ding_space",
    "EDC开通": "edc",
    "有成财务": "finance_info",
    "商务信息表上传": "business_info",
    "钉钉备注": "ding_note",
    "资质寄送情况": "qualification_delivery",
    "确认函": "confirmation_letter",
    "感谢信": "thank_you_letter",
    "报告预计回复报告时间": "report_due",
    "报告跟踪情况": "report_tracking",
    "CAPA预计回复报告时间": "capa_due",
    "CAPA跟踪情况": "capa_tracking",
    "状态": "status_raw",
    "快递单号": "tracking_no",
    "是否定稿": "finalized",
    "回款次数": "payment_count",
    "合同金额": "contract_amount",
    "实际回款金额": "received_amount",
    "是否上传钉钉信息": "ding_uploaded",
}


def _read_source(source: str | Path | bytes | BinaryIO) -> dict[str, pd.DataFrame]:
    if isinstance(source, bytes):
        source = BytesIO(source)
    excel = pd.ExcelFile(source, engine="openpyxl")
    return {
        name: pd.read_excel(excel, sheet_name=name, header=None, dtype=object)
        for name in excel.sheet_names
    }


def _sheet_by_name(
    sheets: Mapping[str, pd.DataFrame],
    exact: str | None = None,
    contains: str | None = None,
) -> pd.DataFrame | None:
    if exact and exact in sheets:
        return sheets[exact]
    if contains:
        matches = [name for name in sheets if contains in name]
        if matches:
            return sheets[sorted(matches)[-1]]
    return None


def _header_dataframe(raw: pd.DataFrame, header_row: int = 0) -> pd.DataFrame:
    if raw.empty or header_row >= len(raw):
        return pd.DataFrame()
    headers: list[str] = []
    counts: dict[str, int] = {}
    for idx, value in enumerate(raw.iloc[header_row].tolist()):
        name = clean_text(value) or f"unnamed_{idx}"
        counts[name] = counts.get(name, 0) + 1
        headers.append(name if counts[name] == 1 else f"{name}_{counts[name]}")
    df = raw.iloc[header_row + 1 :].copy()
    df.columns = headers
    return df.reset_index(drop=True)


def _canonicalize_projects(raw: pd.DataFrame, default_year: int = 2026) -> pd.DataFrame:
    df = _header_dataframe(raw)
    df = df.rename(columns={c: COLUMN_ALIASES[c] for c in df.columns if c in COLUMN_ALIASES})
    required = [
        "project_no",
        "sponsor_project_no",
        "site_name",
        "sponsor_type",
        "phase",
        "disease_area",
        "center_mode",
        "quantity",
        "auditors_raw",
        "case_count",
        "audit_period",
    ]
    for column in required:
        if column not in df.columns:
            df[column] = None
    df = df[required].copy()
    for column in [
        "project_no",
        "sponsor_project_no",
        "site_name",
        "sponsor_type",
        "disease_area",
        "audit_period",
    ]:
        df[column] = df[column].map(clean_text)
    df["phase_raw"] = df["phase"].map(clean_text)
    df["phase"] = df["phase"].map(normalize_phase)
    df["quantity"] = df["quantity"].map(lambda x: numeric_value(x, 1.0)).astype(float)
    df["case_count"] = df["case_count"].map(numeric_value)
    df["auditors"] = df["auditors_raw"].map(split_people)
    dates = df["audit_period"].map(lambda x: parse_date_range(x, default_year))
    df["audit_start"] = [item[0] for item in dates]
    df["audit_end"] = [item[1] for item in dates]
    df["is_reserved"] = (
        df["project_no"].str.match(r"^(?:26)?[A-Z]{2,6}$", na=False)
        & df[["sponsor_project_no", "site_name", "audit_period"]].eq("").all(axis=1)
    )
    df["is_valid"] = df["project_no"].ne("") & df["site_name"].ne("") & ~df["is_reserved"]
    return df.reset_index(drop=True)


def _canonicalize_flows(raw: pd.DataFrame, default_year: int = 2026) -> pd.DataFrame:
    df = _header_dataframe(raw)
    rename = {column: COLUMN_ALIASES[column] for column in df.columns if column in COLUMN_ALIASES}
    rename.update({column: FLOW_NODE_COLUMNS[column] for column in df.columns if column in FLOW_NODE_COLUMNS})
    df = df.rename(columns=rename)
    for column in list(COLUMN_ALIASES.values()) + list(FLOW_NODE_COLUMNS.values()):
        if column not in df.columns:
            df[column] = None
    keep = list(dict.fromkeys(list(COLUMN_ALIASES.values()) + list(FLOW_NODE_COLUMNS.values())))
    df = df[keep].copy()
    for column in df.columns:
        if column not in {"contract_amount", "received_amount", "payment_count", "case_count", "quantity"}:
            df[column] = df[column].map(clean_text)
    df["phase_raw"] = df["phase"].map(clean_text)
    df["phase"] = df["phase"].map(normalize_phase)
    df["auditors"] = df["auditors_raw"].map(split_people)
    dates = df["audit_period"].map(lambda x: parse_date_range(x, default_year))
    df["audit_start"] = [item[0] for item in dates]
    df["audit_end"] = [item[1] for item in dates]
    for column in ["report_due", "capa_due"]:
        df[column] = df[column].map(lambda x: parse_single_date(x, default_year))
    for column in ["case_count", "quantity", "contract_amount", "received_amount", "payment_count"]:
        df[column] = df[column].map(numeric_value)
    df["cra_contact_masked"] = df["cra_contact"].map(mask_phone)
    df["is_valid"] = df["project_no"].ne("") & df["site_name"].ne("")
    return df.reset_index(drop=True)


def _extract_targets(raw: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    months = ["一月", "二月", "三月", "四月", "五月", "六月", "七月", "八月", "九月", "十月", "十一月", "十二月"]
    for i in range(len(raw)):
        month_name = clean_text(raw.iat[i, 0] if raw.shape[1] else None)
        if month_name not in months or i + 3 >= len(raw):
            continue
        plan_label = clean_text(raw.iat[i + 1, 0])
        actual_label = clean_text(raw.iat[i + 2, 0])
        if "计划" not in plan_label or "实际" not in actual_label:
            continue
        plan = numeric_value(raw.iat[i + 1, 5] if raw.shape[1] > 5 else None)
        actual = numeric_value(raw.iat[i + 2, 5] if raw.shape[1] > 5 else None)
        month = months.index(month_name) + 1
        rows.append({"month": month, "month_label": f"{month}月", "plan": plan, "actual": actual})
    result = pd.DataFrame(rows)
    if not result.empty:
        result["achievement_rate"] = result.apply(
            lambda row: row["actual"] / row["plan"] if row["plan"] else None,
            axis=1,
        )
    return result


def _extract_parttime(raw: pd.DataFrame, default_year: int = 2026) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    current_month: int | None = None
    for _, row in raw.iterrows():
        first = clean_text(row.iloc[0] if len(row) else None)
        if first.endswith("月") and first[:-1].isdigit():
            current_month = int(first[:-1])
            continue
        if first in {"姓名", ""}:
            continue
        days = numeric_value(row.iloc[1] if len(row) > 1 else None)
        period = row.iloc[2] if len(row) > 2 else None
        price = numeric_value(row.iloc[3] if len(row) > 3 else None)
        total = numeric_value(row.iloc[4] if len(row) > 4 else None)
        note = clean_text(row.iloc[5] if len(row) > 5 else None)
        if not first or (days == 0 and not clean_text(period)):
            continue
        start, end = parse_date_range(period, default_year)
        rows.append(
            {
                "name_raw": first,
                "name": "协和" if first in {"协和", "协和老师"} else first,
                "month": current_month or (int(start.month) if not pd.isna(start) else None),
                "days": days,
                "period_raw": clean_text(period),
                "start_date": start,
                "end_date": end,
                "unit_price": price,
                "amount": total if total else days * price,
                "note": note,
                "needs_review": bool(note),
            }
        )
    return pd.DataFrame(rows)


def load_bundle(
    weekly_source: str | Path | bytes | BinaryIO | None,
    flow_source: str | Path | bytes | BinaryIO | None,
    default_year: int = 2026,
) -> DataBundle:
    bundle = DataBundle()
    weekly_sheets: dict[str, pd.DataFrame] = {}
    flow_sheets: dict[str, pd.DataFrame] = {}

    if weekly_source is not None:
        weekly_sheets = _read_source(weekly_source)
        bundle.raw_sheets.update({f"周报/{key}": value for key, value in weekly_sheets.items()})
        project_raw = _sheet_by_name(weekly_sheets, exact="4、2026项目原始数据")
        if project_raw is not None:
            bundle.projects = _canonicalize_projects(project_raw, default_year)
        else:
            bundle.warnings.append("未识别到“4、2026项目原始数据”工作表。")
        target_raw = _sheet_by_name(weekly_sheets, exact="1、项目总体汇报")
        if target_raw is not None:
            bundle.targets = _extract_targets(target_raw)
        parttime_raw = _sheet_by_name(weekly_sheets, exact="兼职稽查员统计")
        if parttime_raw is not None:
            bundle.parttime = _extract_parttime(parttime_raw, default_year)

    if flow_source is not None:
        flow_sheets = _read_source(flow_source)
        bundle.raw_sheets.update({f"流程/{key}": value for key, value in flow_sheets.items()})
        flow_raw = _sheet_by_name(
            flow_sheets,
            exact=f"稽查流程管理{default_year}",
            contains="稽查流程管理",
        )
        if flow_raw is not None:
            bundle.flows = _canonicalize_flows(flow_raw, default_year)
        else:
            bundle.warnings.append(f"未识别到“稽查流程管理{default_year}”工作表。")
        multi_raw = _sheet_by_name(flow_sheets, exact="多中心项目进度")
        if multi_raw is not None:
            bundle.multi_center = multi_raw.copy()

    if bundle.projects.empty and not bundle.flows.empty:
        base_columns = [
            "project_no",
            "sponsor_project_no",
            "site_name",
            "sponsor_type",
            "phase",
            "disease_area",
            "center_mode",
            "quantity",
            "auditors_raw",
            "case_count",
            "audit_period",
            "auditors",
            "audit_start",
            "audit_end",
            "is_valid",
        ]
        bundle.projects = bundle.flows[[column for column in base_columns if column in bundle.flows.columns]].copy()

    if not bundle.projects.empty and not bundle.flows.empty:
        enrich_columns = ["project_no", "auditors_raw", "auditors", "audit_period", "audit_start", "audit_end"]
        flow_lookup = bundle.flows.loc[bundle.flows["is_valid"], enrich_columns].drop_duplicates(
            "project_no",
            keep="last",
        )
        merged = bundle.projects.merge(flow_lookup, on="project_no", how="left", suffixes=("", "_flow"))
        for column in ["auditors_raw", "audit_period"]:
            merged[column] = merged[column].where(
                merged[column].map(clean_text).ne(""),
                merged[f"{column}_flow"],
            )
        merged["auditors"] = merged.apply(
            lambda row: row["auditors"]
            if isinstance(row["auditors"], list) and row["auditors"]
            else row["auditors_flow"],
            axis=1,
        )
        for column in ["audit_start", "audit_end"]:
            merged[column] = merged[column].where(merged[column].notna(), merged[f"{column}_flow"])
        bundle.projects = merged.drop(columns=[column for column in merged.columns if column.endswith("_flow")])

    return bundle
