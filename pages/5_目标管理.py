from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from app.analytics import to_frame
from app.ui import apply_page_style, page_header, require_repository, safe_action

st.set_page_config(page_title="目标管理 | TrialAudit Hub", page_icon="🎯", layout="wide")
apply_page_style()
page_header("目标管理", "维护月度计划、实际院次和年度目标")
repo = require_repository()
targets = to_frame(repo.fetch("monthly_targets", order_by="month"))

with st.form("upsert_target"):
    c1, c2, c3, c4, c5 = st.columns(5)
    year = c1.number_input("年度", min_value=2020, max_value=2100, value=date.today().year, step=1)
    month = c2.number_input("月份", min_value=1, max_value=12, value=date.today().month, step=1)
    planned = c3.number_input("计划院次", min_value=0.0, value=0.0, step=1.0)
    actual = c4.number_input("实际院次", min_value=0.0, value=0.0, step=1.0)
    annual_target = c5.number_input("年度目标", min_value=1.0, value=300.0, step=10.0)
    notes = st.text_input("备注")
    if st.form_submit_button("新增或更新目标", type="primary"):
        payload = {"year": year, "month": month, "planned_visits": planned, "actual_visits": actual, "annual_target": annual_target, "notes": notes.strip() or None}
        if safe_action(lambda: repo.upsert_many("monthly_targets", [payload], on_conflict="year,month"), success="目标数据已保存。"):
            st.rerun()

if targets.empty:
    st.info("暂无目标数据。")
    st.stop()

selected_year = st.selectbox("查看年度", sorted(targets["year"].dropna().unique().tolist(), reverse=True))
view = targets[targets["year"] == selected_year].copy().sort_values("month")
view["达成率"] = pd.to_numeric(view["actual_visits"], errors="coerce").fillna(0) / pd.to_numeric(view["planned_visits"], errors="coerce").replace(0, pd.NA)
view["累计计划"] = pd.to_numeric(view["planned_visits"], errors="coerce").fillna(0).cumsum()
view["累计实际"] = pd.to_numeric(view["actual_visits"], errors="coerce").fillna(0).cumsum()

metrics = st.columns(4)
metrics[0].metric("累计计划", f"{view['累计计划'].iloc[-1]:,.0f}")
metrics[1].metric("累计实际", f"{view['累计实际'].iloc[-1]:,.0f}")
metrics[2].metric("累计达成率", f"{view['累计实际'].iloc[-1] / view['累计计划'].iloc[-1]:.1%}" if view['累计计划'].iloc[-1] else "—")
annual = pd.to_numeric(view["annual_target"], errors="coerce").dropna().max() if not view.empty else 300
metrics[3].metric("年度完成率", f"{view['累计实际'].iloc[-1] / annual:.1%}" if annual else "—")

view["月份"] = view["month"].astype(int).astype(str) + "月"
melted = view.melt(id_vars="月份", value_vars=["planned_visits", "actual_visits"], var_name="类型", value_name="院次")
melted["类型"] = melted["类型"].map({"planned_visits": "计划", "actual_visits": "实际"})
st.plotly_chart(px.bar(melted, x="月份", y="院次", color="类型", barmode="group", title=f"{selected_year}年月度计划与实际"), use_container_width=True)
trend = view.melt(id_vars="月份", value_vars=["累计计划", "累计实际"], var_name="类型", value_name="院次")
st.plotly_chart(px.line(trend, x="月份", y="院次", color="类型", markers=True, title="累计进度趋势"), use_container_width=True)
st.dataframe(view[["月份", "planned_visits", "actual_visits", "达成率", "累计计划", "累计实际", "annual_target", "notes"]], use_container_width=True, hide_index=True)
