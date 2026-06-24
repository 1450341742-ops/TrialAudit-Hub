from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app.analytics import dashboard_frames, overdue_flags, parttime_amount
from app.db import get_repository
from app.ui import apply_page_style, connection_badge, page_header, require_repository

st.set_page_config(page_title="TrialAudit Hub", page_icon="📊", layout="wide")
apply_page_style()
page_header("TrialAudit Hub", "临床稽查项目管理与运营分析平台")

repo_preview = get_repository()
with st.sidebar:
    connection_badge(repo_preview)
    st.caption("通过左侧页面导航进入项目、流程、排班、费用、目标和数据导入。")

repo = require_repository()
projects, flows, schedules, parttime, targets = dashboard_frames(repo)
flows_flagged = overdue_flags(flows)

project_count = len(projects)
visit_count = pd.to_numeric(projects.get("visit_count", 0), errors="coerce").fillna(0).sum() if not projects.empty else 0
case_count = pd.to_numeric(projects.get("case_count", 0), errors="coerce").fillna(0).sum() if not projects.empty else 0
annual_target = pd.to_numeric(targets.get("annual_target", 300), errors="coerce").dropna().max() if not targets.empty else 300
completion = visit_count / annual_target if annual_target else 0
report_overdue = int(flows_flagged.get("报告逾期", pd.Series(dtype=bool)).sum()) if not flows_flagged.empty else 0
capa_overdue = int(flows_flagged.get("CAPA逾期", pd.Series(dtype=bool)).sum()) if not flows_flagged.empty else 0

metrics = st.columns(6)
metrics[0].metric("项目记录", f"{project_count:,}")
metrics[1].metric("累计院次", f"{visit_count:,.0f}")
metrics[2].metric("年度完成率", f"{completion:.1%}")
metrics[3].metric("覆盖病例", f"{case_count:,.0f}")
metrics[4].metric("报告逾期", f"{report_overdue}")
metrics[5].metric("CAPA逾期", f"{capa_overdue}")

left, right = st.columns(2)
with left:
    if not targets.empty:
        chart = targets.copy()
        chart["month_label"] = chart["month"].astype(int).astype(str) + "月"
        chart = chart.sort_values("month")
        melted = chart.melt(id_vars="month_label", value_vars=["planned_visits", "actual_visits"], var_name="类型", value_name="院次")
        melted["类型"] = melted["类型"].map({"planned_visits": "计划", "actual_visits": "实际"})
        st.plotly_chart(px.bar(melted, x="month_label", y="院次", color="类型", barmode="group", title="月度计划与实际"), use_container_width=True)
    else:
        st.info("尚未录入月度目标。")
with right:
    if not projects.empty and "therapeutic_area" in projects:
        disease = projects.assign(visit_count=pd.to_numeric(projects["visit_count"], errors="coerce").fillna(0)).groupby("therapeutic_area", dropna=False)["visit_count"].sum().reset_index().sort_values("visit_count", ascending=False).head(10)
        disease["therapeutic_area"] = disease["therapeutic_area"].fillna("未分类")
        st.plotly_chart(px.bar(disease.sort_values("visit_count"), x="visit_count", y="therapeutic_area", orientation="h", title="疾病领域院次 Top 10"), use_container_width=True)
    else:
        st.info("尚无项目结构数据。")

left, right = st.columns(2)
with left:
    if not projects.empty and "status" in projects:
        status = projects.groupby("status", dropna=False).size().reset_index(name="项目数")
        st.plotly_chart(px.pie(status, names="status", values="项目数", hole=.5, title="项目状态分布"), use_container_width=True)
with right:
    if not schedules.empty:
        schedule = schedules.copy()
        schedule["work_date"] = pd.to_datetime(schedule["work_date"], errors="coerce")
        schedule["月份"] = schedule["work_date"].dt.strftime("%Y-%m")
        monthly = schedule.groupby("月份").size().reset_index(name="占用人天")
        st.plotly_chart(px.line(monthly, x="月份", y="占用人天", markers=True, title="稽查员占用人天趋势"), use_container_width=True)

st.subheader("重点待办")
if flows_flagged.empty or not (report_overdue or capa_overdue):
    st.success("当前未识别到报告或CAPA逾期记录。")
else:
    columns = [c for c in ["project_code", "lead_auditor", "report_due_date", "report_status", "capa_due_date", "capa_status", "报告逾期", "CAPA逾期"] if c in flows_flagged]
    st.dataframe(flows_flagged.loc[flows_flagged["报告逾期"] | flows_flagged["CAPA逾期"], columns], use_container_width=True, hide_index=True)

if not parttime.empty:
    parttime = parttime.copy()
    parttime["应付金额"] = parttime_amount(parttime)
    st.caption(f"兼职投入累计：{pd.to_numeric(parttime.get('work_days', 0), errors='coerce').fillna(0).sum():,.1f}天；测算应付金额：¥{parttime['应付金额'].sum():,.2f}")
