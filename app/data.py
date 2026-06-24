from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import BinaryIO

import numpy as np
import pandas as pd

PROJECT_SHEET_CANDIDATES = ["4、2026项目原始数据", "项目原始数据", "项目总体汇报"]
FLOW_SHEET_CANDIDATES = ["稽查流程管理2026", "稽查流程管理2025", "稽查流程管理2024"]
SCHEDULE_SHEET_CANDIDATES = ["2、稽查员行程汇报", "稽查员行程汇报"]
PARTTIME_SHEET_CANDIDATES = ["兼职稽查员统计"]


@dataclass
class WorkbookBundle:
    sheets: dict[str, pd.DataFrame]
    source_name: str


def read_workbook(file: BinaryIO | bytes, source_name: str = "uploaded.xlsx") -> WorkbookBundle:
    payload = file if isinstance(file, bytes) else file.read()
    excel = pd.ExcelFile(io.BytesIO(payload), engine="openpyxl")
    sheets = {name: pd.read_excel(excel, sheet_name=name, header=None) for name in excel.sheet_names}
    return WorkbookBundle(sheets=sheets, source_name=source_name)


def _find_sheet(bundle: WorkbookBundle, candidates: list[str]) -> tuple[str | None, pd.DataFrame | None]:
    for candidate in candidates:
        if candidate in bundle.sheets:
            return candidate, bundle.sheets[candidate].copy()
    for name, frame in bundle.sheets.items():
        if any(candidate in name for candidate in candidates):
            return name, frame.copy()
    return None, None


def _promote_header(frame: pd.DataFrame, required_terms: list[str], scan_rows: int = 12) -> pd.DataFrame:
    for idx in range(min(scan_rows, len(frame))):
        joined = "|".join(frame.iloc[idx].astype(str).str.strip().tolist())
        if any(term in joined for term in required_terms):
            out = frame.iloc[idx + 1 :].copy()
            out.columns = [str(v).strip() if pd.notna(v) else f"未命名_{i}" for i, v in enumerate(frame.iloc[idx])]
            return out.dropna(how="all").reset_index(drop=True)
    return frame.copy()


def normalize_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", "", str(value)).strip()


def normalize_phase(value: object) -> str:
    text = normalize_text(value).replace("Ⅰ", "I").replace("Ⅱ", "II").replace("Ⅲ", "III").upper()
    aliases = {"I期": "I期", "II期": "II期", "III期": "III期", "IV期": "IV期", "II-III期": "II-III期", "II/III期": "II-III期"}
    return aliases.get(text, text or "未填写")


def parse_count(value: object) -> float:
    if pd.isna(value):
        return np.nan
    match = re.search(r"-?\d+(?:\.\d+)?", str(value))
    return float(match.group()) if match else np.nan


def extract_projects(bundle: WorkbookBundle) -> pd.DataFrame:
    _, raw = _find_sheet(bundle, PROJECT_SHEET_CANDIDATES)
    if raw is None:
        return pd.DataFrame()
    df = _promote_header(raw, ["项目编号", "中心名称", "申办方"])
    rename = {" ": "序号", "项目编号": "项目编号", "内部项目编号": "项目编号", "申办方项目编号": "申办方项目编号", "医院": "中心名称", "中心名称": "中心名称", "申办方": "申办方类型", "多单中心": "中心类型", "分期": "分期", "项目类型": "疾病领域", "数量": "院次数", "例": "病例数", "例数": "病例数"}
    df = df.rename(columns={c: rename.get(str(c).strip(), str(c).strip()) for c in df.columns})
    keep = [c for c in ["序号", "项目编号", "申办方项目编号", "中心名称", "申办方类型", "中心类型", "分期", "疾病领域", "院次数", "病例数"] if c in df.columns]
    df = df[keep].copy()
    for col in ["项目编号", "申办方项目编号", "中心名称", "申办方类型", "中心类型", "疾病领域"]:
        if col in df:
            df[col] = df[col].map(lambda x: str(x).strip() if pd.notna(x) else "")
    if "分期" in df:
        df["分期"] = df["分期"].map(normalize_phase)
    df["院次数"] = df["院次数"].map(parse_count).fillna(1) if "院次数" in df else 1
    if "病例数" in df:
        df["病例数"] = df["病例数"].map(parse_count).fillna(0)
    if "项目编号" in df:
        df = df[df["项目编号"].astype(str).str.strip().ne("")]
    return df.reset_index(drop=True)


def extract_flow(bundle: WorkbookBundle) -> pd.DataFrame:
    _, raw = _find_sheet(bundle, FLOW_SHEET_CANDIDATES)
    if raw is None:
        return pd.DataFrame()
    df = _promote_header(raw, ["内部项目编号", "项目编号", "启动函", "EDC"])
    rename = {"内部项目编号": "项目编号", "项目编号": "项目编号", "医院": "中心名称", "中心名称": "中心名称", "参与稽查的老师": "参与稽查员", "组长/撰写人": "组长", "稽查时间": "稽查时间", "例数": "病例数", "EDC是否开通": "EDC状态", "资料": "资料状态"}
    df = df.rename(columns={c: rename.get(str(c).strip(), str(c).strip()) for c in df.columns})
    df = df.loc[:, ~df.columns.duplicated()].copy()
    if "项目编号" not in df:
        return pd.DataFrame()
    df["项目编号"] = df["项目编号"].map(lambda x: str(x).strip() if pd.notna(x) else "")
    return df[df["项目编号"].ne("")].reset_index(drop=True)


def extract_parttime(bundle: WorkbookBundle) -> pd.DataFrame:
    _, raw = _find_sheet(bundle, PARTTIME_SHEET_CANDIDATES)
    if raw is None:
        return pd.DataFrame()
    rows, current_month = [], ""
    for _, row in raw.iterrows():
        first = normalize_text(row.iloc[0]) if len(row) else ""
        if re.fullmatch(r"\d{1,2}月", first):
            current_month = first
            continue
        if first in {"姓名", "", "合计"}:
            continue
        days = parse_count(row.iloc[1] if len(row) > 1 else np.nan)
        if not np.isnan(days):
            rows.append({"月份": current_month or "未识别", "姓名": first, "天数": days, "项目时间": row.iloc[2] if len(row) > 2 else ""})
    return pd.DataFrame(rows)


def extract_schedule(bundle: WorkbookBundle) -> pd.DataFrame:
    _, raw = _find_sheet(bundle, SCHEDULE_SHEET_CANDIDATES)
    if raw is None:
        return pd.DataFrame()
    rows, month = [], ""
    for _, row in raw.iterrows():
        first = normalize_text(row.iloc[0]) if len(row) else ""
        if re.fullmatch(r"\d{1,2}月", first):
            month = first
            continue
        if not month or not first or first in {"姓名", "合计"}:
            continue
        active = sum(1 for value in row.iloc[1:].tolist() if parse_count(value) == 1)
        if active:
            rows.append({"月份": month, "稽查员": first, "行程天数": active})
    return pd.DataFrame(rows)


def node_completion(flow: pd.DataFrame) -> pd.DataFrame:
    if flow.empty:
        return pd.DataFrame(columns=["流程节点", "填写率"])
    rows = []
    for keyword in ["启动函", "资料状态", "EDC状态", "确认函", "感谢信", "报告", "CAPA"]:
        cols = [c for c in flow.columns if keyword.lower() in str(c).lower()]
        if not cols:
            continue
        series = flow[cols].astype(str).replace({"nan": "", "None": ""})
        complete = series.apply(lambda row: any(str(v).strip() for v in row), axis=1).mean()
        rows.append({"流程节点": keyword, "填写率": round(float(complete) * 100, 1)})
    return pd.DataFrame(rows)


def merge_projects_flow(projects: pd.DataFrame, flow: pd.DataFrame) -> pd.DataFrame:
    if projects.empty:
        return flow.copy()
    if flow.empty:
        return projects.copy()
    return projects.merge(flow, on="项目编号", how="left", suffixes=("_项目", "_流程"))


def data_quality(projects: pd.DataFrame, flow: pd.DataFrame) -> pd.DataFrame:
    issues = []
    for table_name, frame in [("项目原始数据", projects), ("流程记录", flow)]:
        if frame.empty:
            issues.append({"数据表": table_name, "问题类型": "未识别", "数量": 1, "说明": "未找到可分析数据"})
            continue
        if "项目编号" in frame:
            issues.append({"数据表": table_name, "问题类型": "重复项目编号记录", "数量": int(frame["项目编号"].duplicated(keep=False).sum()), "说明": "需结合中心判断是否为合理重复"})
            issues.append({"数据表": table_name, "问题类型": "项目编号空白", "数量": int(frame["项目编号"].astype(str).str.strip().eq("").sum()), "说明": "无法进行跨表关联"})
        issues.append({"数据表": table_name, "问题类型": "空白单元格", "数量": int(frame.isna().sum().sum()), "说明": "空白不一定代表流程未完成"})
    return pd.DataFrame(issues)
