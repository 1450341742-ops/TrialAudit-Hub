from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from app.analytics import overdue_flags, to_frame
from app.ui import STATUS_OPTIONS, apply_page_style, page_header, require_repository, safe_action

st.set_page_config(page_title="流程管理 | TrialAudit Hub", page_icon="🔄", layout="wide")
apply_page_style()
page_header("流程管理", "维护启动函、资料、EDC、报告、CAPA和回款等项目节点")
repo = require_repository()
projects = to_frame(repo.fetch("projects", "id,project_code,center_name", order_by="project_code"))
flows = to_frame(repo.fetch("project_flows", order_by="updated_at", descending=True))

if projects.empty:
    st.warning("请先新增或导入项目台账。")
    st.stop()

project_options = {f"{row.project_code}｜{row.center_name or '未填写中心'}": row for row in projects.itertuples(index=False)}
flow_by_project = {row.get("project_id"): row for _, row in flows.iterrows()} if not flows.empty else {}

with st.expander("新增或补建项目流程", expanded=flows.empty):
    with st.form("add_flow"):
        project_label = st.selectbox("关联项目*", list(project_options.keys()))
        project = project_options[project_label]
        c1, c2 = st.columns(2)
        lead_auditor = c1.text_input("组长/撰写人")
        auditors_text = c2.text_input("参与稽查员", placeholder="多人用顿号分隔")
        c1, c2 = st.columns(2)
        audit_start = c1.date_input("稽查开始日期", value=date.today())
        audit_end = c2.date_input("稽查结束日期", value=date.today())
        c1, c2, c3 = st.columns(3)
        materials_status = c1.text_input("资料状态")
        dingpan_status = c2.text_input("钉盘状态")
        edc_status = c3.text_input("EDC状态")
        c1, c2 = st.columns(2)
        report_due = c1.date_input("报告计划日期", value=date.today())
        capa_due = c2.date_input("CAPA计划日期", value=date.today())
        c1, c2 = st.columns(2)
        report_status = c1.text_input("报告跟踪状态")
        capa_status = c2.text_input("CAPA跟踪状态")
        status = st.selectbox("当前流程状态", STATUS_OPTIONS)
        notes = st.text_area("备注")
        submitted = st.form_submit_button("保存流程", type="primary")
        if submitted:
            if project.id in flow_by_project:
                st.error("该项目已存在流程记录，请在下方编辑。")
            else:
                payload = {
                    "project_id": project.id,
                    "project_code": project.project_code,
                    "lead_auditor": lead_auditor.strip() or None,
                    "auditors": [p.strip() for p in auditors_text.replace("，", "、").split("、") if p.strip()],
                    "audit_start_date": audit_start,
                    "audit_end_date": audit_end,
                    "materials_status": materials_status.strip() or None,
                    "dingpan_status": dingpan_status.strip() or None,
                    "edc_status": edc_status.strip() or None,
                    "report_due_date": report_due,
                    "report_status": report_status.strip() or None,
                    "capa_due_date": capa_due,
                    "capa_status": capa_status.strip() or None,
                    "status": status,
                    "notes": notes.strip() or None,
                }
                if safe_action(lambda: repo.insert("project_flows", payload), success="流程记录已新增。"):
                    st.rerun()

if flows.empty:
    st.info("暂无流程记录。")
    st.stop()

flagged = overdue_flags(flows)
metrics = st.columns(4)
metrics[0].metric("流程记录", len(flows))
metrics[1].metric("报告逾期", int(flagged["报告逾期"].sum()))
metrics[2].metric("CAPA逾期", int(flagged["CAPA逾期"].sum()))
metrics[3].metric("已定稿", int(pd.to_numeric(flows.get("finalized", False), errors="coerce").fillna(0).astype(bool).sum()))

only_overdue = st.checkbox("仅显示逾期项目")
view = flagged[flagged["报告逾期"] | flagged["CAPA逾期"]] if only_overdue else flagged
show_cols = [c for c in ["project_code", "lead_auditor", "audit_start_date", "audit_end_date", "materials_status", "dingpan_status", "edc_status", "report_due_date", "report_status", "capa_due_date", "capa_status", "status", "报告逾期", "CAPA逾期", "finalized"] if c in view]
st.dataframe(view[show_cols], use_container_width=True, hide_index=True)

st.subheader("编辑流程")
flow_labels = {str(row.get("project_code")): row for _, row in flows.iterrows()}
selected_code = st.selectbox("选择项目编号", list(flow_labels.keys()))
selected = flow_labels[selected_code]
with st.form("edit_flow"):
    c1, c2 = st.columns(2)
    lead_auditor = c1.text_input("组长/撰写人", value=str(selected.get("lead_auditor") or ""))
    auditors_text = c2.text_input("参与稽查员", value="、".join(selected.get("auditors") or []))
    c1, c2, c3 = st.columns(3)
    materials_status = c1.text_input("资料状态", value=str(selected.get("materials_status") or ""))
    dingpan_status = c2.text_input("钉盘状态", value=str(selected.get("dingpan_status") or ""))
    edc_status = c3.text_input("EDC状态", value=str(selected.get("edc_status") or ""))
    c1, c2 = st.columns(2)
    report_status = c1.text_input("报告跟踪状态", value=str(selected.get("report_status") or ""))
    capa_status = c2.text_input("CAPA跟踪状态", value=str(selected.get("capa_status") or ""))
    c1, c2, c3 = st.columns(3)
    status_value = selected.get("status") if selected.get("status") in STATUS_OPTIONS else STATUS_OPTIONS[0]
    status = c1.selectbox("当前流程状态", STATUS_OPTIONS, index=STATUS_OPTIONS.index(status_value))
    finalized = c2.checkbox("报告已定稿", value=bool(selected.get("finalized")))
    collection_count = c3.number_input("回款次数", min_value=0, value=int(selected.get("collection_count") or 0))
    c1, c2 = st.columns(2)
    contract_amount = c1.number_input("合同金额", min_value=0.0, value=float(selected.get("contract_amount") or 0), step=1000.0)
    received_amount = c2.number_input("实际回款金额", min_value=0.0, value=float(selected.get("received_amount") or 0), step=1000.0)
    notes = st.text_area("备注", value=str(selected.get("notes") or ""))
    update = st.form_submit_button("保存修改", type="primary")
    if update:
        payload = {
            "lead_auditor": lead_auditor.strip() or None,
            "auditors": [p.strip() for p in auditors_text.replace("，", "、").split("、") if p.strip()],
            "materials_status": materials_status.strip() or None,
            "dingpan_status": dingpan_status.strip() or None,
            "edc_status": edc_status.strip() or None,
            "report_status": report_status.strip() or None,
            "capa_status": capa_status.strip() or None,
            "status": status,
            "finalized": finalized,
            "collection_count": collection_count,
            "contract_amount": contract_amount,
            "received_amount": received_amount,
            "notes": notes.strip() or None,
        }
        if safe_action(lambda: repo.update("project_flows", selected["id"], payload), success="流程已更新。"):
            st.rerun()
