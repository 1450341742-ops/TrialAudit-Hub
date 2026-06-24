from __future__ import annotations

import streamlit as st

from app.db import DatabaseOperationError, SupabaseRepository, get_repository


STATUS_OPTIONS = ["待确认", "待排班", "已排班", "稽查中", "待报告", "待CAPA", "已完成", "已取消", "历史导入"]
RISK_OPTIONS = ["低", "中", "高"]
SPONSOR_TYPES = ["内资", "外资", "未分类"]
CENTER_TYPES = ["单中心", "多中心", "未分类"]
EMPLOYMENT_TYPES = ["正式", "兼职", "合作"]
PAYMENT_STATUS_OPTIONS = ["待确认", "待支付", "部分支付", "已支付", "无需支付"]


def apply_page_style() -> None:
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.2rem; padding-bottom: 2.2rem; max-width: 1500px;}
        [data-testid="stMetric"] {background:#f7f9fc;border:1px solid #e5eaf1;padding:14px;border-radius:12px;}
        div[data-testid="stForm"] {border:1px solid #e5eaf1;border-radius:12px;padding:1rem;}
        .db-ok {padding:.65rem .8rem;border-radius:10px;background:#ecfdf3;color:#027a48;border:1px solid #abefc6;}
        .db-warn {padding:.65rem .8rem;border-radius:10px;background:#fffaeb;color:#b54708;border:1px solid #fedf89;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, description: str) -> None:
    st.title(title)
    st.caption(description)


def require_repository() -> SupabaseRepository:
    repo = get_repository()
    if repo is None:
        st.warning("尚未连接 Supabase。请先进入“系统设置”配置项目地址和服务端密钥，并在 Supabase SQL Editor 中执行 `supabase/schema.sql`。")
        st.stop()
    try:
        repo.healthcheck()
    except DatabaseOperationError as exc:
        st.error(f"Supabase 已配置，但数据库暂不可用：{exc}")
        st.info("请确认已执行数据库建表脚本，且密钥具有服务端写入权限。")
        st.stop()
    return repo


def connection_badge(repo: SupabaseRepository | None) -> None:
    if repo is None:
        st.markdown('<div class="db-warn">Supabase：未配置</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="db-ok">Supabase：已配置（{repo.settings.key_source}）</div>', unsafe_allow_html=True)


def safe_action(action, *, success: str) -> bool:
    try:
        action()
        st.success(success)
        return True
    except DatabaseOperationError as exc:
        st.error(str(exc))
        return False
