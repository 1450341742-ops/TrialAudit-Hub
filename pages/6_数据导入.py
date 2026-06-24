from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from app.data import data_quality, extract_flow, extract_monthly_targets, extract_parttime, extract_projects, extract_schedule, read_workbook
from app.importer import import_workbooks
from app.ui import apply_page_style, page_header, require_repository

st.set_page_config(page_title="数据导入 | TrialAudit Hub", page_icon="⬆️", layout="wide")
apply_page_style()
page_header("数据导入", "将现有Excel清洗后批量写入Supabase，并可将原文件存档到私有Storage")
repo = require_repository()

c1, c2, c3 = st.columns(3)
weekly_file = c1.file_uploader("项目管理部每周汇报表", type=["xlsx"], key="weekly_import")
flow_file = c2.file_uploader("中心稽查项目流程记录表", type=["xlsx"], key="flow_import")
year = c3.number_input("导入年度", min_value=2020, max_value=2100, value=2026, step=1)
annual_target = st.number_input("年度目标院次", min_value=1, value=300, step=10)
archive_source = st.checkbox("同时将原始Excel存档到Supabase私有Storage", value=True)

weekly_bundle = read_workbook(weekly_file.getvalue(), weekly_file.name) if weekly_file else None
flow_bundle = read_workbook(flow_file.getvalue(), flow_file.name) if flow_file else None

if not weekly_bundle and not flow_bundle:
    st.info("请至少上传一份Excel。系统不会将原始文件提交到GitHub。")
else:
    projects = extract_projects(weekly_bundle) if weekly_bundle else pd.DataFrame()
    schedule = extract_schedule(weekly_bundle, year=year) if weekly_bundle else pd.DataFrame()
    parttime = extract_parttime(weekly_bundle, year=year) if weekly_bundle else pd.DataFrame()
    targets = extract_monthly_targets(weekly_bundle, year=year, annual_target=annual_target) if weekly_bundle else pd.DataFrame()
    flow = extract_flow(flow_bundle or weekly_bundle, preferred_year=year) if (flow_bundle or weekly_bundle) else pd.DataFrame()

    metrics = st.columns(5)
    metrics[0].metric("项目记录", len(projects))
    metrics[1].metric("流程记录", len(flow))
    metrics[2].metric("排班日记录", len(schedule))
    metrics[3].metric("兼职记录", len(parttime))
    metrics[4].metric("月度目标", len(targets))

    tabs = st.tabs(["项目预览", "流程预览", "排班预览", "兼职预览", "目标预览", "质量检查"])
    preview_frames = [projects, flow, schedule, parttime, targets, data_quality(projects, flow)]
    for tab, frame in zip(tabs, preview_frames):
        with tab:
            st.dataframe(frame.head(200), use_container_width=True, hide_index=True)
            if len(frame) > 200:
                st.caption(f"仅预览前200行，共{len(frame)}行。")

    confirm = st.checkbox("确认将以上数据写入Supabase；相同项目编号和来源键将自动更新，不重复新增")
    if st.button("开始导入", type="primary", disabled=not confirm):
        try:
            with st.spinner("正在清洗并写入数据库..."):
                counts = import_workbooks(repo, weekly_bundle, flow_bundle, year=year, annual_target=annual_target)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                for uploaded, data_type in [(weekly_file, "weekly_report"), (flow_file, "project_flow")]:
                    if uploaded is None:
                        continue
                    storage_path = None
                    if archive_source:
                        storage_path = f"{year}/{timestamp}_{uploaded.name}"
                        repo.upload_bytes("source-files", storage_path, uploaded.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    repo.insert("import_batches", {
                        "file_name": uploaded.name,
                        "data_type": data_type,
                        "storage_path": storage_path,
                        "row_count": sum(counts.values()),
                        "success_count": sum(counts.values()),
                        "failed_count": 0,
                        "notes": str(counts),
                    })
            st.success("导入完成。")
            st.json(counts)
        except Exception as exc:
            st.error(f"导入失败：{exc}")
            st.info("请确认已执行 `supabase/schema.sql`，并使用服务端 service_role 密钥。")

st.subheader("历史导入记录")
try:
    history = pd.DataFrame(repo.fetch("import_batches", order_by="imported_at", descending=True, limit=100))
    if history.empty:
        st.caption("暂无导入记录。")
    else:
        st.dataframe(history, use_container_width=True, hide_index=True)
except Exception as exc:
    st.warning(f"暂时无法读取导入历史：{exc}")
