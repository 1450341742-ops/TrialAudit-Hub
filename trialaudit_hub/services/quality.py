from __future__ import annotations

import pandas as pd

from .normalization import clean_text


def build_quality_report(projects: pd.DataFrame, flows: pd.DataFrame, parttime: pd.DataFrame) -> pd.DataFrame:
    issues: list[dict[str, object]] = []
    if not projects.empty:
        identity_columns = [column for column in ["project_no", "sponsor_project_no", "site_name"] if column in projects.columns]
        active = projects[
            projects[identity_columns].fillna("").astype(str).apply(lambda row: any(item.strip() for item in row), axis=1)
        ]
        for idx, row in active.iterrows():
            project_no = clean_text(row.get("project_no"))
            site = clean_text(row.get("site_name"))
            if not project_no:
                issues.append({"level": "阻断", "category": "项目编号", "record": f"行{idx + 2}", "message": "项目编号缺失"})
            if project_no and not site:
                issues.append({"level": "阻断", "category": "中心名称", "record": project_no, "message": "中心名称缺失"})
            start_date, end_date = row.get("audit_start"), row.get("audit_end")
            if project_no and site and (pd.isna(start_date) or pd.isna(end_date)):
                issues.append({"level": "提醒", "category": "日期", "record": project_no, "message": "稽查日期无法解析或为空"})
            elif not pd.isna(start_date) and not pd.isna(end_date) and end_date < start_date:
                issues.append({"level": "阻断", "category": "日期", "record": project_no, "message": "结束日期早于开始日期"})
            if project_no and clean_text(row.get("phase")) == "待确认":
                issues.append({"level": "提醒", "category": "分期", "record": project_no, "message": "项目分期待确认"})
        eligible = active[active["project_no"].ne("")]
        duplicates = eligible.duplicated(["project_no", "site_name", "audit_period"], keep=False)
        for _, row in eligible[duplicates].iterrows():
            issues.append({
                "level": "高风险",
                "category": "重复项目",
                "record": clean_text(row.get("project_no")),
                "message": "同项目、同中心、同稽查时间存在重复记录",
            })
    if not flows.empty:
        eligible_flows = flows[flows["project_no"].ne("")]
        duplicate_ids = eligible_flows.duplicated("project_no", keep=False)
        for _, row in eligible_flows[duplicate_ids].iterrows():
            issues.append({
                "level": "提醒",
                "category": "流程项目编号",
                "record": clean_text(row.get("project_no")),
                "message": "流程表中项目编号重复，请确认是否为不同轮次",
            })
    if not parttime.empty and "needs_review" in parttime:
        for _, row in parttime[parttime["needs_review"]].iterrows():
            issues.append({
                "level": "提醒",
                "category": "兼职费用",
                "record": clean_text(row.get("name")),
                "message": clean_text(row.get("note")) or "费用待核对",
            })
    result = pd.DataFrame(issues, columns=["level", "category", "record", "message"])
    if not result.empty:
        order = pd.Categorical(result["level"], ["阻断", "高风险", "提醒", "提示"], ordered=True)
        result = result.assign(_order=order).sort_values(["_order", "category"]).drop(columns="_order")
    return result.reset_index(drop=True)
