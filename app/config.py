from __future__ import annotations

import os
from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class SupabaseSettings:
    url: str
    key: str
    key_source: str

    @property
    def configured(self) -> bool:
        return bool(self.url and self.key)


def _secret(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or "").strip()


def get_supabase_settings() -> SupabaseSettings:
    session_url = str(st.session_state.get("supabase_url", "") or "").strip()
    session_key = str(st.session_state.get("supabase_key", "") or "").strip()
    if session_url and session_key:
        return SupabaseSettings(session_url, session_key, "当前会话")

    url = os.getenv("SUPABASE_URL", "").strip() or _secret("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or _secret("SUPABASE_SERVICE_ROLE_KEY")
    fallback_key = os.getenv("SUPABASE_KEY", "").strip() or _secret("SUPABASE_KEY")
    key = service_key or fallback_key
    source = "环境变量/Streamlit Secrets" if url and key else "未配置"
    return SupabaseSettings(url, key, source)
