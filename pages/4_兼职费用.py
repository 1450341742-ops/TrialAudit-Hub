from __future__ import annotations

import hashlib
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from app.analytics import parttime_amount, to_frame
from app.ui import PAYMENT_STATUS_OPTIONS, apply_page_style, page_header, require_repository, safe_action

st.set_page_config(page_title="兼职费用 | TrialAudit Hub", page_icon="💰", layout="wide")
apply_page_style()
page_header("兼职费用", "记录兼职稽查员投入、单价、调整金额和支付状态")
repo = require_repository()
auditors = to_frame(repo.fetch("auditors", order_by="name"))
projects = to_frame(repo.fetch("projects", "id,project_code,center_name", order_by="project_code"))
entries = to_frame(repo.fetch("parttime_entries", order_by="period_month", descending=True))

parttime_names = auditors.loc[auditors.get("employment_type", pd.Series(dtype=object)).isin(["兼职", "合作"]), "name"].tolist() if not auditors.empty else []
project_options = {"不关联项目": None}
if not projects.empty:
    project_options.update({f"{row.project_code}｜{row.center_name or '未填写中心'}": row for row in projects.itertuples(index=False)})

with st.expander("新增兼职费用记录", expanded=True):
    with st.form("add_parttime", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        auditor_name = c1.selectbox("兼职稽查员", parttime_names + ["手工输入"] if parttime_names else ["手工输入"])
        manual_name = c2.text_input("手工姓名", disabled=auditor_name != "手工输入")
        period_month = c3.date_input("费用月份", value=date.today().replace(day=1))
        c1, c2, c3 = st.columns(3)
        work_start = c1.date_input("开始日期", value=date.today())
        work_end = c2.date_input("结束日期", value=date.today())
        work_days = c3.number_input("计费天数", min_value=0.0, value=1.0, step=0.5)
        c1, c2, c3 = st.columns(3)
        daily_rate = c1.number_input("日单价", min_value=0.0, value=0.0, step=100.0)
        adjustment = c2.number_input("调整金额", value=0.0, step=100.0)
        actual_paid = c3.number_input("实际支付金额", min_value=0.0, value=0.0, step=100.0)
        c1, c2 = st.columns(2)
        payment_status = c1.selectbox("付款状态", PAYMENT_STATUS_OPTIONS)
        project_label = c2.selectbox("关联项目", list(project_options.keys()))
        notes = st.text_area("备注")
        submitted = st.form_submit_button("保存费用", type="primary")
        if submitted:
            name = manual_name.strip() if auditor_name == "手工输入" else auditor_name
            if not name:
                st.error("兼职稽查员姓名不能为空。")
            else:
                project = project_options[project_label]
                source_key = hashlib.sha1(f"manual|{name}|{period_month}|{work_start}|{work_end}|{getattr(project, 'project_code', '')}".encode("utf-8")).hexdigest()
                payload = {
                    "source_key": source_key,
                    "auditor_name": name,
                    "project_id": getattr(project, "id", None),
                    "project_code": getattr(project, "project_code", None),
                    "period_month": period_month.replace(day=1),
                    "work_start_date": work_start,
                    "work_end_date": work_end,
                    "work_days": work_days,
                    "daily_rate": daily_rate,
                    "adjustment_amount": adjustment,
                    "actual_paid": actual_paid,
                    "payment_status": payment_status,
                    "notes": notes.strip() or None,
                }
                if safe_action(lambda: repo.upsert_many("parttime_entries", [payload], on_conflict="source_key"), success="兼职费用已保存。"):
                    st.rerun()

if entries.empty:
    st.info("暂无兼职费用记录。")
    st.stop()

entries = entries.copy()
entries["period_month"] = pd.to_datetime(entries["period_month"], errors="coerce")
entries["应付金额"] = parttime_amount(entries)
metrics = st.columns(4)
metrics[0].metric("累计计费天数", f"{pd.to_numeric(entries['work_days'], errors='coerce').fillna(0).sum():,.1f}")
metrics[1].metric("累计应付", f"¥{entries['应付金额'].sum():,.2f}")
metrics[2].metric("累计实付", f"¥{pd.to_numeric(entries['actual_paid'], errors='coerce').fillna(0).sum():,.2f}")
metrics[3].metric("待支付记录", int(entries["payment_status"].isin(["待确认", "待支付", "部分支付"]).sum()))

monthly = entries.assign(月份=entries["period_month"].dt.strftime("%Y-%m")).groupby("月份").agg(计费天数=("work_days", "sum"), 应付金额=("应付金额", "sum")).reset_index()
left, right = st.columns(2)
with left:
    st.plotly_chart(px.bar(monthly, x="月份", y="计费天数", title="兼职投入趋势"), use_container_width=True)
with right:
    ranking = entries.groupby("auditor_name")["应付金额"].sum().reset_index().sort_values("应付金额")
    st.plotly_chart(px.bar(ranking, x="应付金额", y="auditor_name", orientation="h", title="兼职费用排名"), use_container_width=True)
show_cols = [c for c in ["period_month", "auditor_name", "project_code", "work_start_date", "work_end_date", "work_days", "daily_rate", "adjustment_amount", "应付金额", "actual_paid", "payment_status", "notes"] if c in entries]
st.dataframe(entries[show_cols], use_container_width=True, hide_index=True)

st.subheader("更新付款状态")
labels = {f"{row.get('period_month')}｜{row.get('auditor_name')}｜{row.get('project_code') or '无项目'}": row for _, row in entries.iterrows()}
selected_label = st.selectbox("选择费用记录", list(labels.keys()))
selected = labels[selected_label]
with st.form("update_payment"):
    current = selected.get("payment_status") if selected.get("payment_status") in PAYMENT_STATUS_OPTIONS else PAYMENT_STATUS_OPTIONS[0]
    payment_status = st.selectbox("付款状态", PAYMENT_STATUS_OPTIONS, index=PAYMENT_STATUS_OPTIONS.index(current))
    actual_paid = st.number_input("实际支付金额", min_value=0.0, value=float(selected.get("actual_paid") or 0), step=100.0)
    payment_date = st.date_input("付款日期", value=date.today())
    if st.form_submit_button("保存付款信息", type="primary"):
        if safe_action(lambda: repo.update("parttime_entries", selected["id"], {"payment_status": payment_status, "actual_paid": actual_paid, "payment_date": payment_date}), success="付款信息已更新。"):
            st.rerun()
