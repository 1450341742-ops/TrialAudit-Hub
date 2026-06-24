from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import BinaryIO

import numpy as np
import pandas as pd

PROJECT_SHEET_CANDIDATES = ["4、2026项目原始数据", "项目原始数据", "项目总体汇报"]
FLOW_SHEET_CANDIDATES = ["稽查流程管理2026", "稽查流程管理2025", "稽查流程管理2024", "稽查流程管理2023"]
SCHEDULE_SHEET_CANDIDATES = ["2、稽查员行程汇报", "稽查员行程汇报"]
PARTTIME_SHEET_CANDIDATES = ["兼职稽查员统计"]
TARGET_SHEET_CANDIDATES = ["1、项目总体汇报", "项目总体汇报"]

MONTH_MAP = {
    "一月": 1,
    "二月": 2,
    "三月": 3,
    "四月": 4,
    "五月": 5,
    "六月": 6,
    "七月": 7,
    "八月": 8,
    "九月": 9,
    "十月": 10,
    "十一月": 11,
    "十二月": 12,
}


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
        values = frame.iloc[idx].astype(str).str.strip().tolist()
        joined = "|".join(values)
        if any(term in joined for term in required_terms):
            out = frame.iloc[idx + 1 :].copy()
            headers: list[str] = []
            seen: dict[str, int] = {}
            for i, value in enumerate(frame.iloc[idx]):
                name = str(value).strip() if pd.notna(value) else f"未命名_{i}"
                seen[name] = seen.get(name, 0) + 1
                if seen[name] > 1:
                    name = f"{name}_{seen[name]}"
                headers.append(name)
            out.columns = headers
            return out.dropna(how="all").reset_index(drop=True)
    return frame.copy()


def normalize_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"\s+", "", str(value)).strip()


def normalize_phase(value: object) -> str:
    text = normalize_text(value).replace("Ⅰ", "I").replace("Ⅱ", "II").replace("Ⅲ", "III").replace("Ⅳ", "IV").upper()
    aliases = {
        "I期": "I期",
        "II期": "II期",
        "III期": "III期",
        "IV期": "IV期",
        "II-III期": "II-III期",
        "II/III期": "II-III期",
        "III期/IV期": "III-IV期",
        "IIIB期": "IIIb期",
        "IIB期": "IIb期",
    }
    return aliases.get(text, text or "未填写")


def parse_count(value: object) -> float:
    if value is None or pd.isna(value):
        return np.nan
    match = re.search(r"-?\d+(?:\.\d+)?", str(value))
    return float(match.group()) if match else np.nan


def split_people(value: object) -> list[str]:
    text = str(value or "").strip()
    if not text or text.lower() == "nan":
        return []
    parts = re.split(r"[、,，;；/\n]+", text)
    return list(dict.fromkeys(p.strip() for p in parts if p.strip()))


def parse_date_value(value: object, year_hint: int = 2026) -> date | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and 30000 <= float(value) <= 80000:
        return (datetime(1899, 12, 30) + timedelta(days=float(value))).date()
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    text = text.replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")
    try:
        parsed = pd.to_datetime(text, errors="raise")
        if isinstance(parsed, pd.Timestamp):
            if parsed.year == 1900 and year_hint:
                return date(year_hint, parsed.month, parsed.day)
            return parsed.date()
    except Exception:
        pass
    match = re.search(r"(?:(\d{4})[-.]?)?(\d{1,2})[-.](\d{1,2})", text)
    if match:
        year = int(match.group(1) or year_hint)
        try:
            return date(year, int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None
    return None


def parse_chinese_date_range(value: object, year_hint: int = 2026, month_hint: int | None = None) -> tuple[date | None, date | None]:
    if value is None or pd.isna(value):
        return None, None
    if isinstance(value, (pd.Timestamp, datetime, date, int, float)):
        parsed = parse_date_value(value, year_hint)
        return parsed, parsed
    text = str(value).strip().replace("—", "-").replace("–", "-").replace("至", "-")
    full = re.search(r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日?\s*-\s*(?:(\d{1,2})月)?(\d{1,2})日?", text)
    if full:
        year = int(full.group(1) or year_hint)
        start_month = int(full.group(2))
        end_month = int(full.group(4) or start_month)
        try:
            return date(year, start_month, int(full.group(3))), date(year, end_month, int(full.group(5)))
        except ValueError:
            return None, None
    short = re.search(r"(\d{1,2})月(\d{1,2})\s*-\s*(\d{1,2})日?", text)
    if short:
        try:
            month = int(short.group(1))
            return date(year_hint, month, int(short.group(2))), date(year_hint, month, int(short.group(3)))
        except ValueError:
            return None, None
    day_only = re.search(r"(\d{1,2})\s*-\s*(\d{1,2})日?", text)
    if day_only and month_hint:
        try:
            return date(year_hint, month_hint, int(day_only.group(1))), date(year_hint, month_hint, int(day_only.group(2)))
        except ValueError:
            return None, None
    parsed = parse_date_value(value, year_hint)
    return parsed, parsed


def _string(value: object) -> str:
    return "" if value is None or pd.isna(value) else str(value).strip()


def extract_projects(bundle: WorkbookBundle) -> pd.DataFrame:
    _, raw = _find_sheet(bundle, PROJECT_SHEET_CANDIDATES)
    if raw is None:
        return pd.DataFrame()
    df = _promote_header(raw, ["项目编号", "中心名称", "申办方"])
    rename = {
        " ": "序号",
        "": "序号",
        "项目编号": "项目编号",
        "内部项目编号": "项目编号",
        "申办方项目编号": "申办方项目编号",
        "医院": "中心名称",
        "中心名称": "中心名称",
        "申办方": "申办方类型",
        "多单中心": "中心类型",
        "分期": "分期",
        "项目类型": "疾病领域",
        "数量": "院次数",
        "例": "病例数",
        "例数": "病例数",
    }
    df = df.rename(columns={c: rename.get(str(c).strip(), str(c).strip()) for c in df.columns})
    keep = [c for c in ["序号", "项目编号", "申办方项目编号", "中心名称", "申办方类型", "中心类型", "分期", "疾病领域", "院次数", "病例数"] if c in df.columns]
    df = df[keep].copy()
    for col in ["项目编号", "申办方项目编号", "中心名称", "申办方类型", "中心类型", "疾病领域"]:
        if col in df:
            df[col] = df[col].map(_string)
    if "分期" in df:
        df["分期"] = df["分期"].map(normalize_phase)
    df["院次数"] = df["院次数"].map(parse_count).fillna(1) if "院次数" in df else 1
    if "病例数" in df:
        df["病例数"] = df["病例数"].map(parse_count).fillna(0)
    else:
        df["病例数"] = 0
    if "项目编号" not in df:
        return pd.DataFrame()
    return df[df["项目编号"].astype(str).str.strip().ne("")].reset_index(drop=True)


def extract_flow(bundle: WorkbookBundle, preferred_year: int = 2026) -> pd.DataFrame:
    preferred = f"稽查流程管理{preferred_year}"
    candidates = [preferred] + [c for c in FLOW_SHEET_CANDIDATES if c != preferred]
    sheet_name, raw = _find_sheet(bundle, candidates)
    if raw is None:
        return pd.DataFrame()
    df = _promote_header(raw, ["内部项目编号", "项目编号", "启动函", "EDC"])
    rename = {
        "内部项目编号": "项目编号",
        "项目编号": "项目编号",
        "医院": "中心名称",
        "中心名称": "中心名称",
        "参与稽查的老师": "参与稽查员",
        "组长/撰写人": "组长",
        "稽查时间": "稽查时间",
        "例数": "病例数",
        "EDC是否开通": "EDC状态",
        "EDC开通": "EDC状态",
        "资料": "资料状态",
        "是否创建钉盘": "钉盘状态",
        "是否上传钉钉": "钉盘状态",
        "是否上传钉钉信息": "钉钉信息状态",
        "项目类型": "疾病领域",
        "数量": "院次数",
        "状态": "项目状态",
        "是否定稿": "定稿状态",
    }
    df = df.rename(columns={c: rename.get(str(c).strip(), str(c).strip()) for c in df.columns})
    df = df.loc[:, ~df.columns.duplicated()].copy()
    if "项目编号" not in df:
        return pd.DataFrame()
    df["项目编号"] = df["项目编号"].map(_string)
    df = df[df["项目编号"].ne("")].reset_index(drop=True)
    df.attrs["source_sheet"] = sheet_name
    df.attrs["source_year"] = preferred_year
    return df


def extract_schedule(bundle: WorkbookBundle, year: int = 2026) -> pd.DataFrame:
    _, raw = _find_sheet(bundle, SCHEDULE_SHEET_CANDIDATES)
    if raw is None:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    current_month: int | None = None
    day_numbers: list[int | None] = []
    for _, row in raw.iterrows():
        first = normalize_text(row.iloc[0]) if len(row) else ""
        month_match = re.fullmatch(r"(\d{1,2})月", first)
        if month_match:
            current_month = int(month_match.group(1))
            day_numbers = []
            for value in row.iloc[1:].tolist():
                match = re.search(r"(\d{1,2})", normalize_text(value))
                day_numbers.append(int(match.group(1)) if match else None)
            continue
        if current_month is None or not first or first in {"姓名", "合计", "总计"}:
            continue
        for day_number, value in zip(day_numbers, row.iloc[1:].tolist()):
            if day_number is None or parse_count(value) != 1:
                continue
            try:
                work_date = date(year, current_month, day_number)
            except ValueError:
                continue
            rows.append({"月份": f"{current_month}月", "稽查员": first, "工作日期": work_date, "状态": "占用"})
    return pd.DataFrame(rows)


def extract_parttime(bundle: WorkbookBundle, year: int = 2026) -> pd.DataFrame:
    _, raw = _find_sheet(bundle, PARTTIME_SHEET_CANDIDATES)
    if raw is None:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    current_month: int | None = None
    for _, row in raw.iterrows():
        first = normalize_text(row.iloc[0]) if len(row) else ""
        month_match = re.fullmatch(r"(\d{1,2})月", first)
        if month_match:
            current_month = int(month_match.group(1))
            continue
        if first in {"姓名", "", "合计", "总计"}:
            continue
        days = parse_count(row.iloc[1] if len(row) > 1 else np.nan)
        if np.isnan(days):
            continue
        period_text = _string(row.iloc[2] if len(row) > 2 else "")
        start, end = parse_chinese_date_range(period_text, year_hint=year, month_hint=current_month)
        rows.append({
            "月份": f"{current_month}月" if current_month else "未识别",
            "月份数字": current_month,
            "姓名": first,
            "天数": days,
            "项目时间": period_text,
            "开始日期": start,
            "结束日期": end,
        })
    return pd.DataFrame(rows)


def extract_monthly_targets(bundle: WorkbookBundle, year: int = 2026, annual_target: int = 300) -> pd.DataFrame:
    _, raw = _find_sheet(bundle, TARGET_SHEET_CANDIDATES)
    if raw is None:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for idx in range(len(raw) - 2):
        label = normalize_text(raw.iloc[idx, 0])
        if label not in MONTH_MAP:
            continue
        plan_label = normalize_text(raw.iloc[idx + 1, 0])
        actual_label = normalize_text(raw.iloc[idx + 2, 0])
        if "计划" not in plan_label or "实际" not in actual_label:
            continue
        month = MONTH_MAP[label]
        planned = parse_count(raw.iloc[idx + 1, 5] if raw.shape[1] > 5 else np.nan)
        actual = parse_count(raw.iloc[idx + 2, 5] if raw.shape[1] > 5 else np.nan)
        rows.append({
            "年度": year,
            "月份": month,
            "计划院次": 0 if np.isnan(planned) else planned,
            "实际院次": 0 if np.isnan(actual) else actual,
            "年度目标": annual_target,
        })
    return pd.DataFrame(rows)


def node_completion(flow: pd.DataFrame) -> pd.DataFrame:
    if flow.empty:
        return pd.DataFrame(columns=["流程节点", "填写率"])
    keywords = ["启动函", "资料状态", "钉盘状态", "EDC状态", "确认函", "感谢信", "报告", "CAPA"]
    rows = []
    for keyword in keywords:
        cols = [c for c in flow.columns if keyword.lower() in str(c).lower()]
        if not cols:
            continue
        series = flow[cols].astype(str).replace({"nan": "", "None": "", "NaT": ""})
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
    issues: list[dict[str, object]] = []
    for table_name, frame in [("项目原始数据", projects), ("流程记录", flow)]:
        if frame.empty:
            issues.append({"数据表": table_name, "问题类型": "未识别", "数量": 1, "说明": "未找到可分析数据"})
            continue
        if "项目编号" in frame:
            dup = int(frame["项目编号"].duplicated(keep=False).sum())
            issues.append({"数据表": table_name, "问题类型": "重复项目编号记录", "数量": dup, "说明": "需结合中心判断是否为合理重复"})
            blank = int(frame["项目编号"].astype(str).str.strip().eq("").sum())
            issues.append({"数据表": table_name, "问题类型": "项目编号空白", "数量": blank, "说明": "无法进行跨表关联"})
        blank_cells = int(frame.isna().sum().sum())
        issues.append({"数据表": table_name, "问题类型": "空白单元格", "数量": blank_cells, "说明": "空白不一定代表流程未完成"})
    return pd.DataFrame(issues)
