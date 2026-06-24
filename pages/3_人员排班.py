from __future__ import annotations

import hashlib
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from app.analytics import to_frame
from app.ui import EMPLOYMENT_TYPES, apply_page_style, page_header, require_repository, safe_action

st.set_page_config(page_title="人员排班 | TrialAudit Hub", page_icon="📅", layout="wide")
apply_page_style()
page_header("人员排班", "维护稽查员档案、每日占用状态和项目安排")
repo = require_repository()
auditors = to_frame(repo.fetch("auditors", order_by="name"))
projects = to_frame(repo.fetch("projects", "id,project_code,center_name", order_by="project_code"))
schedules = to_frame(repo.fetch("schedules", order_by="work_date", descending=True))

left, right = st.columns([1, 2])
with left:
    with st.expander("新增稽查员", expanded=auditors.empty):
        with st.form("add_auditor", clear_on_submit=True):
            name = st.text_input("姓名*")
            employment_type = st.selectbox("人员类型", EMPLOYMENT_TYPES)
            level = st.text_input("能力等级")
            monthly_limit = st.number_input("月度院次上限", min_value=1, value=4, step=1)
            phone = st.text_input("联系电话")
            notes = st.text_area("备注")
            submitted = st.form_submit_button("保存人员", type="primary")
            if submitted:
                if not name.strip():
                    st.error("姓名不能为空。")
                else:
                    payload = {
                        "name": name.strip(),
                        "employment_type": employment_type,
                        "level": level.strip() or None,
                        "monthly_visit_limit": monthly_limit,
                        "active": True,
                        "phone": phone.strip() or None,
                        "notes": notes.strip() or None,
                    }
                    if safe_action(lambda: repo.insert("auditors", payload), success="稽查员已新增。"):
                        st.rerun()
with right:
    if not auditors.empty:
        show = [c for c in ["name", "employment_type", "level", "monthly_visit_limit", "active", "phone"] if c in auditors]
        st.dataframe(auditors[show], use_container_width=True, hide_index=True)
    else:
        st.info("暂无人员档案。")

if auditors.empty:
    st.stop()

project_options = {"不关联项目": None}
if not projects.empty:
    project_options.update({f"{row.project_code}｜{row.center_name or '未填写中心'}": row for row in projects.itertuples(index=False)})

with st.expander("新增排班记录", expanded=True):
    with st.form("add_schedule", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        auditor_name = c1.selectbox("稽查员*", auditors["name"].tolist())
        work_date = c2.date_input("日期", value=date.today())
        availability_status = c3.selectbox("状态", ["占用", "可用", "休假", "培训", "差旅"])
        c1, c2, c3 = st.columns(3)
        project_label = c1.selectbox("关联项目", list(project_options.keys()))
        role = c2.text_input("项目角色", placeholder="组长/组员")
        city = c3.text_input("城市")
        notes = st.text_area("备注")
        submitted = st.form_submit_button("保存排班", type="primary")
        if submitted:
            project = project_options[project_label]
            source_key = hashlib.sha1(f"manual|{auditor_name}|{work_date}|{getattr(project, 'project_code', '')}".encode("utf-8")).hexdigest()
            payload = {
                "source_key": source_key,
                "auditor_name": auditor_name,
                "auditor_id": auditors.loc[auditors["name"] == auditor_name, "id"].iloc[0],
                "project_id": getattr(project, "id", None),
                "project_code": getattr(project, "project_code", None),
                "work_date": work_date,
                "availability_status": availability_status,
                "role": role.strip() or None,
                "city": city.strip() or None,
                "notes": notes.strip() or None,
            }
            if safe_action(lambda: repo.upsert_many("schedules", [payload], on_conflict="source_key"), success="排班记录已保存。"):
                st.rerun()

if schedules.empty:
    st.info("暂无排班记录。")
    st.stop()

schedule = schedules.copy()
schedule["work_date"] = pd.to_datetime(schedule["work_date"], errors="coerce")
schedule["月份"] = schedule["work_date"].dt.strftime("%Y-%m")
months = sorted(schedule["月份"].dropna().unique().tolist(), reverse=True)
selected_month = st.selectbox("查看月份", months)
month_view = schedule[schedule["月份"] == selected_month].copy()

metrics = st.columns(3)
metrics[0].metric("本月排班记录", len(month_view))
metrics[1].metric("涉及人员", month_view["auditor_name"].nunique())
conflicts = month_view.groupby(["auditor_name", "work_date"]).size().reset_index(name="数量")
metrics[2].metric("重复日期冲突", int((conflicts["数量"] > 1).sum()))

load = month_view.groupby("auditor_name").size().reset_index(name="行程天数").sort_values("行程天数")
st.plotly_chart(px.bar(load, x="行程天数", y="auditor_name", orientation="h", title=f"{selected_month}人员负荷"), use_container_width=True)
show_cols = [c for c in ["work_date", "auditor_name", "project_code", "availability_status", "role", "city", "notes"] if c in month_view]
st.dataframe(month_view.sort_values(["work_date", "auditor_name"])[show_cols], use_container_width=True, hide_index=True)

st.subheader("删除排班记录")
labels = {f"{row.get('work_date')}｜{row.get('auditor_name')}｜{row.get('project_code') or '无项目'}": row for _, row in schedules.iterrows()}
selected_label = st.selectbox("选择记录", list(labels.keys()))
selected = labels[selected_label]
confirm = st.checkbox("确认删除所选排班记录")
if st.button("删除排班", disabled=not confirm):
    if safe_action(lambda: repo.delete("schedules", selected["id"]), success="排班记录已删除。"):
        st.rerun()
