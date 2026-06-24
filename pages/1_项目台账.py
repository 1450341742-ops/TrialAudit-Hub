from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from app.analytics import to_frame
from app.ui import CENTER_TYPES, RISK_OPTIONS, SPONSOR_TYPES, STATUS_OPTIONS, apply_page_style, page_header, require_repository, safe_action

st.set_page_config(page_title="项目台账 | TrialAudit Hub", page_icon="📋", layout="wide")
apply_page_style()
page_header("项目台账", "查看、筛选并人工新增或维护临床稽查项目")
repo = require_repository()
projects = to_frame(repo.fetch("projects", order_by="updated_at", descending=True))

with st.expander("新增项目", expanded=projects.empty):
    with st.form("add_project", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        project_code = c1.text_input("内部项目编号*", placeholder="WNRH-TE001-26001")
        sponsor_project_code = c2.text_input("申办方/方案编号")
        center_name = c3.text_input("中心名称")
        c1, c2, c3, c4 = st.columns(4)
        sponsor_type = c1.selectbox("申办方类型", SPONSOR_TYPES)
        center_type = c2.selectbox("中心类型", CENTER_TYPES)
        phase = c3.text_input("分期")
        therapeutic_area = c4.text_input("疾病领域")
        c1, c2, c3, c4 = st.columns(4)
        visit_count = c1.number_input("院次数", min_value=0.0, value=1.0, step=1.0)
        case_count = c2.number_input("病例数", min_value=0, value=0, step=1)
        status = c3.selectbox("项目状态", STATUS_OPTIONS)
        risk_level = c4.selectbox("风险等级", RISK_OPTIONS)
        c1, c2 = st.columns(2)
        project_manager = c1.text_input("项目经理")
        source_year = c2.number_input("所属年度", min_value=2020, max_value=2100, value=date.today().year)
        notes = st.text_area("备注")
        submitted = st.form_submit_button("保存项目", type="primary")
        if submitted:
            if not project_code.strip():
                st.error("内部项目编号不能为空。")
            else:
                payload = {
                    "project_code": project_code.strip(),
                    "sponsor_project_code": sponsor_project_code.strip() or None,
                    "center_name": center_name.strip() or None,
                    "sponsor_type": sponsor_type,
                    "center_type": center_type,
                    "phase": phase.strip() or None,
                    "therapeutic_area": therapeutic_area.strip() or None,
                    "visit_count": visit_count,
                    "case_count": case_count,
                    "project_manager": project_manager.strip() or None,
                    "status": status,
                    "risk_level": risk_level,
                    "source_year": source_year,
                    "notes": notes.strip() or None,
                }
                if safe_action(lambda: repo.insert("projects", payload), success="项目已新增。"):
                    st.rerun()

if projects.empty:
    st.info("暂无项目数据，可通过上方表单新增，或进入“数据导入”批量导入Excel。")
    st.stop()

filters = st.columns(4)
keyword = filters[0].text_input("搜索项目编号/中心/疾病领域")
status_filter = filters[1].multiselect("项目状态", sorted(projects["status"].dropna().unique().tolist()) if "status" in projects else [])
risk_filter = filters[2].multiselect("风险等级", sorted(projects["risk_level"].dropna().unique().tolist()) if "risk_level" in projects else [])
year_filter = filters[3].multiselect("年度", sorted(projects["source_year"].dropna().unique().tolist()) if "source_year" in projects else [])

view = projects.copy()
if keyword:
    cols = [c for c in ["project_code", "center_name", "therapeutic_area", "sponsor_project_code"] if c in view]
    mask = view[cols].astype(str).apply(lambda col: col.str.contains(keyword, case=False, na=False)).any(axis=1)
    view = view[mask]
if status_filter:
    view = view[view["status"].isin(status_filter)]
if risk_filter:
    view = view[view["risk_level"].isin(risk_filter)]
if year_filter:
    view = view[view["source_year"].isin(year_filter)]

show_cols = [c for c in ["project_code", "sponsor_project_code", "center_name", "sponsor_type", "center_type", "phase", "therapeutic_area", "visit_count", "case_count", "project_manager", "status", "risk_level", "source_year", "updated_at"] if c in view]
st.dataframe(view[show_cols], use_container_width=True, hide_index=True)

st.subheader("编辑或删除项目")
labels = {f"{row.get('project_code')}｜{row.get('center_name') or '未填写中心'}": row for _, row in projects.iterrows()}
selected_label = st.selectbox("选择项目", list(labels.keys()))
selected = labels[selected_label]
with st.form("edit_project"):
    c1, c2, c3 = st.columns(3)
    sponsor_project_code = c1.text_input("申办方/方案编号", value=str(selected.get("sponsor_project_code") or ""))
    center_name = c2.text_input("中心名称", value=str(selected.get("center_name") or ""))
    project_manager = c3.text_input("项目经理", value=str(selected.get("project_manager") or ""))
    c1, c2, c3, c4 = st.columns(4)
    sponsor_type = c1.selectbox("申办方类型", SPONSOR_TYPES, index=SPONSOR_TYPES.index(selected.get("sponsor_type")) if selected.get("sponsor_type") in SPONSOR_TYPES else 0)
    center_type = c2.selectbox("中心类型", CENTER_TYPES, index=CENTER_TYPES.index(selected.get("center_type")) if selected.get("center_type") in CENTER_TYPES else 0)
    phase = c3.text_input("分期", value=str(selected.get("phase") or ""))
    therapeutic_area = c4.text_input("疾病领域", value=str(selected.get("therapeutic_area") or ""))
    c1, c2, c3, c4 = st.columns(4)
    visit_count = c1.number_input("院次数", min_value=0.0, value=float(selected.get("visit_count") or 0), step=1.0)
    case_count = c2.number_input("病例数", min_value=0, value=int(selected.get("case_count") or 0), step=1)
    status_value = selected.get("status") if selected.get("status") in STATUS_OPTIONS else STATUS_OPTIONS[0]
    status = c3.selectbox("项目状态", STATUS_OPTIONS, index=STATUS_OPTIONS.index(status_value))
    risk_value = selected.get("risk_level") if selected.get("risk_level") in RISK_OPTIONS else RISK_OPTIONS[0]
    risk_level = c4.selectbox("风险等级", RISK_OPTIONS, index=RISK_OPTIONS.index(risk_value))
    notes = st.text_area("备注", value=str(selected.get("notes") or ""))
    update = st.form_submit_button("保存修改", type="primary")
    if update:
        payload = {
            "sponsor_project_code": sponsor_project_code.strip() or None,
            "center_name": center_name.strip() or None,
            "project_manager": project_manager.strip() or None,
            "sponsor_type": sponsor_type,
            "center_type": center_type,
            "phase": phase.strip() or None,
            "therapeutic_area": therapeutic_area.strip() or None,
            "visit_count": visit_count,
            "case_count": case_count,
            "status": status,
            "risk_level": risk_level,
            "notes": notes.strip() or None,
        }
        if safe_action(lambda: repo.update("projects", selected["id"], payload), success="项目已更新。"):
            st.rerun()

confirm = st.checkbox("确认删除所选项目及其关联流程数据")
if st.button("删除项目", disabled=not confirm):
    if safe_action(lambda: repo.delete("projects", selected["id"]), success="项目已删除。"):
        st.rerun()
