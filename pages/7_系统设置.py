from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.config import get_supabase_settings
from app.db import get_repository
from app.ui import apply_page_style, connection_badge, page_header

st.set_page_config(page_title="系统设置 | TrialAudit Hub", page_icon="⚙️", layout="wide")
apply_page_style()
page_header("系统设置", "配置Supabase连接、初始化数据库并检查运行状态")

repo = get_repository()
connection_badge(repo)
settings = get_supabase_settings()
if settings.configured:
    st.caption(f"当前配置来源：{settings.key_source}；项目地址：{settings.url}")

st.subheader("临时连接配置")
st.caption("以下密钥只保存在当前Streamlit会话中。正式部署请使用Streamlit Secrets，不要写入代码或GitHub。")
with st.form("session_credentials"):
    url = st.text_input("SUPABASE_URL", value=str(st.session_state.get("supabase_url", "")), placeholder="https://xxxx.supabase.co")
    key = st.text_input("SUPABASE_SERVICE_ROLE_KEY", value="", type="password")
    save = st.form_submit_button("保存到当前会话并测试", type="primary")
    if save:
        st.session_state["supabase_url"] = url.strip()
        st.session_state["supabase_key"] = key.strip()
        st.cache_resource.clear()
        st.rerun()

c1, c2 = st.columns(2)
if c1.button("测试数据库连接"):
    current = get_repository()
    if current is None:
        st.error("尚未配置Supabase。")
    else:
        try:
            current.healthcheck()
            st.success("Supabase连接正常，projects表可访问。")
        except Exception as exc:
            st.error(f"连接失败：{exc}")
if c2.button("清除当前会话密钥"):
    st.session_state.pop("supabase_url", None)
    st.session_state.pop("supabase_key", None)
    st.cache_resource.clear()
    st.rerun()

st.subheader("正式部署配置")
st.code('''SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "YOUR_SERVICE_ROLE_KEY"''', language="toml")
st.caption("在Streamlit Community Cloud的应用设置中进入 Secrets，粘贴以上配置。service_role密钥只应放在服务端Secrets中。")

st.subheader("数据库初始化")
schema_path = Path(__file__).resolve().parents[1] / "supabase" / "schema.sql"
if schema_path.exists():
    schema = schema_path.read_text(encoding="utf-8")
    st.download_button("下载Supabase建表脚本", schema.encode("utf-8"), "trialaudit_schema.sql", "text/sql")
    with st.expander("查看SQL脚本"):
        st.code(schema, language="sql")
else:
    st.error("未找到 supabase/schema.sql。")

st.markdown("""
1. 在Supabase创建项目。
2. 打开 **SQL Editor**，执行本页提供的建表脚本。
3. 在 **Project Settings → API Keys** 获取服务端密钥。
4. 将URL和密钥加入Streamlit Secrets。
5. 进入“数据导入”上传两份Excel并写入数据库。
""")
