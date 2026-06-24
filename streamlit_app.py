from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app.data import data_quality, extract_flow, extract_parttime, extract_projects, extract_schedule, merge_projects_flow, node_completion, read_workbook

st.set_page_config(page_title="TrialAudit Hub", page_icon="📊", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 1.4rem; padding-bottom: 2rem;}
[data-testid="stMetric"] {background: #f7f9fc; border: 1px solid #e7ebf2; padding: 14px; border-radius: 12px;}
</style>
""", unsafe_allow_html=True)

st.title("TrialAudit Hub")
st.caption("临床稽查项目管理与运营分析平台 · MVP")

with st.sidebar:
    st.header("数据导入")
    weekly_file = st.file_uploader("上传项目管理部每周汇报表", type=["xlsx"], key="weekly")
    flow_file = st.file_uploader("上传中心稽查项目流程记录表", type=["xlsx"], key="flow")
    annual_target = st.number_input("年度目标院次", min_value=1, value=300, step=10)
    st.info("系统只读取上传文件，不修改原Excel。")

if not weekly_file and not flow_file:
    st.info("请在左侧上传至少一份Excel。上传两份文件后可进行项目编号联动分析。")
    st.stop()

weekly_bundle = read_workbook(weekly_file, weekly_file.name) if weekly_file else None
flow_bundle = read_workbook(flow_file, flow_file.name) if flow_file else None
projects = extract_projects(weekly_bundle) if weekly_bundle else pd.DataFrame()
schedule = extract_schedule(weekly_bundle) if weekly_bundle else pd.DataFrame()
parttime = extract_parttime(weekly_bundle) if weekly_bundle else pd.DataFrame()
flow = extract_flow(flow_bundle) if flow_bundle else pd.DataFrame()
if flow.empty and weekly_bundle:
    flow = extract_flow(weekly_bundle)
merged = merge_projects_flow(projects, flow)

pages = st.tabs(["经营驾驶舱", "项目结构", "流程节点", "人员负荷", "兼职投入", "数据质量", "明细查询"])

with pages[0]:
    total_visits = float(projects["院次数"].sum()) if "院次数" in projects else float(len(projects))
    total_cases = float(projects["病例数"].sum()) if "病例数" in projects else 0
    completion = total_visits / annual_target if annual_target else 0
    matched = projects["项目编号"].isin(flow["项目编号"]).sum() if not projects.empty and not flow.empty else 0
    cols = st.columns(5)
    cols[0].metric("已识别院次", f"{total_visits:,.0f}")
    cols[1].metric("年度目标", f"{annual_target:,.0f}")
    cols[2].metric("年度完成率", f"{completion:.1%}")
    cols[3].metric("覆盖病例数", f"{total_cases:,.0f}")
    cols[4].metric("跨表匹配记录", f"{matched:,.0f}")
    left, right = st.columns(2)
    with left:
        if not projects.empty and "申办方类型" in projects:
            chart = projects.groupby("申办方类型", dropna=False)["院次数"].sum().reset_index()
            st.plotly_chart(px.pie(chart, names="申办方类型", values="院次数", hole=.55, title="内外资院次结构"), use_container_width=True)
    with right:
        if not projects.empty and "中心类型" in projects:
            chart = projects.groupby("中心类型", dropna=False)["院次数"].sum().reset_index()
            st.plotly_chart(px.pie(chart, names="中心类型", values="院次数", hole=.55, title="单中心/多中心结构"), use_container_width=True)
    st.subheader("管理摘要")
    observations = []
    if completion < .3:
        observations.append(f"当前识别完成率为 {completion:.1%}，需结合统计截止日期判断年度进度是否偏离。")
    if matched:
        observations.append(f"项目记录中有 {matched} 条能够在流程表中通过项目编号匹配，可进一步定位流程瓶颈。")
    if not schedule.empty:
        top = schedule.sort_values("行程天数", ascending=False).iloc[0]
        observations.append(f"当前识别的最高月度行程负荷为 {top['稽查员']}，{top['月份']}共{int(top['行程天数'])}天。")
    for item in observations or ["当前数据不足以形成稳定结论，请补充两份Excel后重新分析。"]:
        st.write("- " + item)

with pages[1]:
    if projects.empty:
        st.warning("未识别到项目原始数据。")
    else:
        dimensions = [c for c in ["疾病领域", "分期", "申办方类型", "中心类型"] if c in projects]
        selected = st.selectbox("分析维度", dimensions)
        chart = projects.groupby(selected, dropna=False)["院次数"].sum().reset_index().sort_values("院次数", ascending=True)
        st.plotly_chart(px.bar(chart, x="院次数", y=selected, orientation="h", title=f"{selected}院次分布"), use_container_width=True)
        st.dataframe(chart.sort_values("院次数", ascending=False), use_container_width=True, hide_index=True)

with pages[2]:
    if flow.empty:
        st.warning("未识别到流程记录数据。")
    else:
        completion_df = node_completion(flow)
        if completion_df.empty:
            st.info("已识别流程表，但未找到标准流程节点字段。")
        else:
            st.plotly_chart(px.bar(completion_df, x="流程节点", y="填写率", range_y=[0, 100], title="流程节点字段填写率（不等同业务完成率）"), use_container_width=True)
            st.dataframe(completion_df, use_container_width=True, hide_index=True)
        st.caption("流程字段空白只能说明未填写或未识别，不能直接判定业务节点未完成。")

with pages[3]:
    if schedule.empty:
        st.warning("未识别到稽查员行程数据。")
    else:
        filtered_month = st.selectbox("选择月份", sorted(schedule["月份"].unique()))
        view = schedule[schedule["月份"] == filtered_month].sort_values("行程天数", ascending=True)
        st.plotly_chart(px.bar(view, x="行程天数", y="稽查员", orientation="h", title=f"{filtered_month}稽查员行程负荷"), use_container_width=True)
        view = view.assign(负荷状态=pd.cut(view["行程天数"], bins=[-1, 14, 17, 999], labels=["正常", "关注", "高负荷"]))
        st.dataframe(view.sort_values("行程天数", ascending=False), use_container_width=True, hide_index=True)

with pages[4]:
    if parttime.empty:
        st.warning("未识别到兼职稽查员统计。")
    else:
        monthly = parttime.groupby("月份", dropna=False)["天数"].sum().reset_index()
        ranking = parttime.groupby("姓名", dropna=False)["天数"].sum().reset_index().sort_values("天数", ascending=True)
        left, right = st.columns(2)
        with left:
            st.plotly_chart(px.bar(monthly, x="月份", y="天数", title="兼职投入月度趋势"), use_container_width=True)
        with right:
            st.plotly_chart(px.bar(ranking, x="天数", y="姓名", orientation="h", title="兼职人员投入排名"), use_container_width=True)
        daily_rate = st.number_input("测算日单价（可选）", min_value=0.0, value=0.0, step=100.0)
        if daily_rate:
            st.metric("估算兼职费用", f"¥{parttime['天数'].sum() * daily_rate:,.2f}")

with pages[5]:
    st.dataframe(data_quality(projects, flow), use_container_width=True, hide_index=True)
    st.caption("数据质量检查仅提示风险，不会修改上传文件。")

with pages[6]:
    source = st.radio("选择明细", ["项目数据", "流程数据", "联动数据"], horizontal=True)
    frame = {"项目数据": projects, "流程数据": flow, "联动数据": merged}[source]
    keyword = st.text_input("按项目编号、中心或申办方关键字查询")
    if keyword and not frame.empty:
        mask = frame.astype(str).apply(lambda col: col.str.contains(keyword, case=False, na=False)).any(axis=1)
        frame = frame[mask]
    st.dataframe(frame, use_container_width=True, hide_index=True)
    st.download_button("导出当前明细CSV", frame.to_csv(index=False).encode("utf-8-sig"), "trialaudit_export.csv", "text/csv")
