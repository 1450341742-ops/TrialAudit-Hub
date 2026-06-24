from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from trialaudit_hub.services import (
    build_quality_report,
    calculate_kpis,
    export_analysis,
    flow_with_status,
    generate_management_summary,
    load_bundle,
    monthly_plan_actual,
    node_completion,
    staff_load,
)

st.set_page_config(
    page_title="TrialAudit Hub",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
.block-container {padding-top: 1.4rem; padding-bottom: 2rem;}
[data-testid="stMetric"] {background: #f7f9fc; border: 1px solid #e7edf5; padding: 14px; border-radius: 12px;}
[data-testid="stMetricLabel"] {font-weight: 600;}
.small-note {color: #667085; font-size: 0.88rem;}
.section-title {font-weight: 700; font-size: 1.15rem; margin: 0.4rem 0 0.8rem 0;}
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def parse_uploaded_files(weekly_bytes: bytes | None, flow_bytes: bytes | None, year: int):
    return load_bundle(weekly_bytes, flow_bytes, default_year=year)


def percent(value: float | None) -> str:
    return "—" if value is None or pd.isna(value) else f"{value:.1%}"


def show_empty_state() -> None:
    st.info("请在左侧上传《项目管理部每周汇报表》和《中心稽查项目流程记录表》。系统不会把文件保存到仓库。")
    st.markdown(
        """
首版支持：
- 自动识别项目原始数据、目标计划、流程节点和兼职费用；
- 生成经营驾驶舱、项目流程、人员负荷和数据质量分析；
- 导出结构化分析结果；
- 生成有指标依据的管理分析摘要。
"""
    )


with st.sidebar:
    st.title("TrialAudit Hub")
    st.caption("Clinical Audit Operations Analytics")
    st.divider()
    year = st.number_input("数据年度", min_value=2020, max_value=2100, value=2026, step=1)
    annual_target = st.number_input("年度目标院次", min_value=0, value=300, step=10)
    selected_month = st.selectbox("分析月份", options=list(range(1, 13)), index=max(0, min(11, date.today().month - 1)), format_func=lambda x: f"{x}月")
    weekly_file = st.file_uploader("项目管理部每周汇报表", type=["xlsx", "xlsm"], key="weekly")
    flow_file = st.file_uploader("中心稽查项目流程记录表", type=["xlsx", "xlsm"], key="flow")
    st.caption("敏感联系人默认脱敏展示；上传文件仅在当前会话中处理。")

weekly_bytes = weekly_file.getvalue() if weekly_file else None
flow_bytes = flow_file.getvalue() if flow_file else None

st.title("TrialAudit Hub")
st.caption("临床稽查项目管理与运营分析系统 · MVP V0.1")

if not weekly_bytes and not flow_bytes:
    show_empty_state()
    st.stop()

with st.spinner("正在识别工作表并计算指标……"):
    bundle = parse_uploaded_files(weekly_bytes, flow_bytes, int(year))

for warning in bundle.warnings:
    st.warning(warning)

if bundle.projects.empty and bundle.flows.empty:
    st.error("没有识别到可分析的项目数据，请确认上传文件包含目标工作表。")
    st.stop()

kpis = calculate_kpis(
    bundle.projects,
    bundle.flows,
    bundle.targets,
    bundle.parttime,
    annual_target=int(annual_target),
    year=int(year),
    month=int(selected_month),
)
monthly = monthly_plan_actual(bundle.projects, bundle.targets, int(year))
flow_status = flow_with_status(bundle.flows)
load = staff_load(bundle.projects)
quality = build_quality_report(bundle.projects, bundle.flows, bundle.parttime)
node_df = node_completion(bundle.flows)

nav = st.tabs(["经营驾驶舱", "项目台账", "流程跟踪", "人员负荷", "兼职成本", "数据质量", "管理分析"])

with nav[0]:
    cols = st.columns(6)
    cols[0].metric("年度目标", f"{kpis.annual_target} 院次")
    cols[1].metric("累计完成", f"{kpis.completed} 院次")
    cols[2].metric("年度完成率", percent(kpis.annual_rate))
    cols[3].metric(f"{selected_month}月计划", f"{kpis.current_month_plan} 院次")
    cols[4].metric(f"{selected_month}月实际", f"{kpis.current_month_actual} 院次")
    cols[5].metric(f"{selected_month}月达成率", percent(kpis.current_month_rate))

    cols = st.columns(6)
    cols[0].metric("进行中/已排班", kpis.ongoing_projects)
    cols[1].metric("待报告", kpis.pending_reports)
    cols[2].metric("报告逾期", kpis.overdue_reports)
    cols[3].metric("待CAPA", kpis.pending_capa)
    cols[4].metric("高负荷人员", kpis.high_load_people)
    cols[5].metric("本月兼职费用", f"¥{kpis.parttime_cost:,.0f}")

    left, right = st.columns(2)
    with left:
        fig = go.Figure()
        fig.add_bar(x=monthly["month_label"], y=monthly["plan"], name="计划院次")
        fig.add_bar(x=monthly["month_label"], y=monthly["actual"], name="实际院次")
        fig.update_layout(title="月度计划与实际", barmode="group", height=360, margin=dict(l=20, r=20, t=55, b=20))
        st.plotly_chart(fig, use_container_width=True)
    with right:
        fig = go.Figure()
        fig.add_scatter(x=monthly["month_label"], y=monthly["cumulative_plan"], mode="lines+markers", name="累计计划")
        fig.add_scatter(x=monthly["month_label"], y=monthly["cumulative_actual"], mode="lines+markers", name="累计实际")
        fig.update_layout(title="累计目标与完成趋势", height=360, margin=dict(l=20, r=20, t=55, b=20))
        st.plotly_chart(fig, use_container_width=True)

    project_data = bundle.projects[bundle.projects.get("is_valid", True)].copy()
    c1, c2, c3 = st.columns(3)
    with c1:
        sponsor = project_data["sponsor_type"].replace("", "待确认").value_counts().reset_index()
        sponsor.columns = ["category", "count"]
        st.plotly_chart(px.pie(sponsor, names="category", values="count", hole=0.48, title="内资/外资分布"), use_container_width=True)
    with c2:
        phase = project_data["phase"].replace("", "待确认").value_counts().head(10).reset_index()
        phase.columns = ["category", "count"]
        st.plotly_chart(px.bar(phase, x="category", y="count", title="项目分期分布"), use_container_width=True)
    with c3:
        disease = project_data["disease_area"].replace("", "待确认").value_counts().head(10).sort_values().reset_index()
        disease.columns = ["category", "count"]
        st.plotly_chart(px.bar(disease, x="count", y="category", orientation="h", title="疾病领域 Top 10"), use_container_width=True)

    if not flow_status.empty:
        c1, c2 = st.columns(2)
        with c1:
            status = flow_status["derived_status"].value_counts().reset_index()
            status.columns = ["status", "count"]
            st.plotly_chart(px.bar(status, x="status", y="count", title="项目状态分布"), use_container_width=True)
        with c2:
            if not node_df.empty:
                view = node_df.copy()
                view["完成率"] = view["completion_rate"] * 100
                st.plotly_chart(px.bar(view, x="node", y="完成率", range_y=[0, 100], title="流程节点记录完成率（%）"), use_container_width=True)

with nav[1]:
    st.subheader("项目统一台账")
    projects = bundle.projects.copy()
    f1, f2, f3, f4 = st.columns(4)
    sponsor_filter = f1.multiselect("申办方类型", sorted(projects["sponsor_type"].dropna().astype(str).unique()))
    phase_filter = f2.multiselect("分期", sorted(projects["phase"].dropna().astype(str).unique()))
    disease_filter = f3.multiselect("疾病领域", sorted(projects["disease_area"].dropna().astype(str).unique()))
    keyword = f4.text_input("项目/中心关键词")
    filtered = projects.copy()
    if sponsor_filter:
        filtered = filtered[filtered["sponsor_type"].isin(sponsor_filter)]
    if phase_filter:
        filtered = filtered[filtered["phase"].isin(phase_filter)]
    if disease_filter:
        filtered = filtered[filtered["disease_area"].isin(disease_filter)]
    if keyword:
        mask = filtered[["project_no", "sponsor_project_no", "site_name"]].astype(str).apply(lambda col: col.str.contains(keyword, case=False, na=False)).any(axis=1)
        filtered = filtered[mask]
    display_cols = ["project_no", "sponsor_project_no", "site_name", "sponsor_type", "phase", "disease_area", "case_count", "audit_start", "audit_end", "auditors_raw", "is_valid"]
    st.dataframe(filtered[[c for c in display_cols if c in filtered]], use_container_width=True, hide_index=True)
    st.caption(f"当前筛选：{len(filtered)}条；有效项目：{int(filtered.get('is_valid', pd.Series(dtype=bool)).sum()) if 'is_valid' in filtered else len(filtered)}条。")

with nav[2]:
    st.subheader("项目流程跟踪")
    if flow_status.empty:
        st.info("未上传或未识别流程记录表。")
    else:
        risk_only = st.checkbox("仅看逾期或待处理项目", value=False)
        view = flow_status.copy()
        if risk_only:
            view = view[(view["report_overdue_days"] > 0) | (view["capa_overdue_days"] > 0) | view["derived_status"].isin(["待报告", "待CAPA", "待确认"])]
        cols = [
            "project_no", "sponsor_project_no", "site_name", "audit_start", "audit_end", "derived_status",
            "kickoff_letter", "materials", "ding_space", "edc", "confirmation_letter", "report_due",
            "report_tracking", "report_overdue_days", "capa_due", "capa_tracking", "capa_overdue_days", "finalized",
        ]
        st.dataframe(view[[c for c in cols if c in view]], use_container_width=True, hide_index=True)
        st.caption("空白字段表示系统未记录或待确认，不直接等同于业务未完成。")

with nav[3]:
    st.subheader("稽查员排班与负荷")
    if load.empty:
        st.info("项目中未识别到可计算的人员和日期信息。")
    else:
        month_load = load[load["month"].eq(selected_month)].copy()
        fig = px.bar(month_load.sort_values("journey_days"), x="journey_days", y="person", orientation="h", color="load_level", title=f"{selected_month}月人员行程天数")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(month_load, use_container_width=True, hide_index=True)
        conflicts = month_load[month_load["conflict_days"] > 0]
        if not conflicts.empty:
            st.warning(f"检测到{len(conflicts)}名人员存在同日多项目冲突，请下钻核对。")

with nav[4]:
    st.subheader("兼职人员与成本")
    if bundle.parttime.empty:
        st.info("未识别到兼职稽查员统计数据。")
    else:
        parttime = bundle.parttime.copy()
        monthly_cost = parttime.groupby("month", dropna=False).agg(兼职天数=("days", "sum"), 费用=("amount", "sum")).reset_index()
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(px.bar(monthly_cost, x="month", y="费用", title="月度兼职费用"), use_container_width=True)
        with c2:
            ranking = parttime.groupby("name").agg(兼职天数=("days", "sum"), 费用=("amount", "sum")).sort_values("费用").reset_index()
            st.plotly_chart(px.bar(ranking, x="费用", y="name", orientation="h", title="兼职人员费用排名"), use_container_width=True)
        st.dataframe(parttime, use_container_width=True, hide_index=True)
        review_count = int(parttime["needs_review"].sum())
        if review_count:
            st.warning(f"共有{review_count}条费用备注需要人工核对，系统未自动修改金额。")

with nav[5]:
    st.subheader("数据质量中心")
    if quality.empty:
        st.success("当前未识别到明显的数据质量问题。")
    else:
        summary = quality["level"].value_counts().reset_index()
        summary.columns = ["level", "count"]
        st.plotly_chart(px.bar(summary, x="level", y="count", title="异常等级分布"), use_container_width=True)
        st.dataframe(quality, use_container_width=True, hide_index=True)

with nav[6]:
    st.subheader("管理分析摘要")
    summary_text = generate_management_summary(
        bundle,
        annual_target=int(annual_target),
        year=int(year),
        month=int(selected_month),
    )
    st.text_area("可复制到周报或月度经营复盘", value=summary_text, height=330)
    analysis_file = export_analysis(bundle, annual_target=int(annual_target), year=int(year))
    st.download_button(
        "下载分析结果 Excel",
        data=analysis_file,
        file_name=f"TrialAudit_Hub_{year}_{selected_month:02d}_analysis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    st.caption("导出文件包含目标与实际、项目台账、流程分析、人员负荷、兼职费用、节点完成率和数据质量明细。")
