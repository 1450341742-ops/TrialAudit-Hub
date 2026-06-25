from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable

import numpy as np
import pandas as pd
import streamlit as st
from supabase import Client, create_client

from app.config import SupabaseSettings, get_supabase_settings


class DatabaseNotConfigured(RuntimeError):
    pass


class DatabaseOperationError(RuntimeError):
    pass


def _clean_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and np.isnan(value):
        return None
    if pd.isna(value) if not isinstance(value, (list, tuple, dict)) else False:
        return None
    if isinstance(value, tuple):
        return [_clean_value(v) for v in value]
    if isinstance(value, list):
        return [_clean_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _clean_value(v) for k, v in value.items()}
    return value


def clean_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: _clean_value(value) for key, value in record.items()}


@st.cache_resource(show_spinner=False)
def _build_client(url: str, key: str) -> Client:
    return create_client(url, key)


@dataclass
class SupabaseRepository:
    client: Client
    settings: SupabaseSettings

    def healthcheck(self) -> bool:
        try:
            self.client.table("projects").select("id").limit(1).execute()
            return True
        except Exception as exc:
            raise DatabaseOperationError(str(exc)) from exc

    def fetch(
        self,
        table: str,
        columns: str = "*",
        *,
        order_by: str | None = None,
        descending: bool = False,
        limit: int = 5000,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        try:
            query = self.client.table(table).select(columns)
            for key, value in (filters or {}).items():
                if value is not None:
                    query = query.eq(key, value)
            if order_by:
                query = query.order(order_by, desc=descending)
            response = query.limit(limit).execute()
            return list(response.data or [])
        except Exception as exc:
            raise DatabaseOperationError(f"读取 {table} 失败：{exc}") from exc

    def insert(self, table: str, record: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.client.table(table).insert(clean_record(record)).execute()
            rows = list(response.data or [])
            return rows[0] if rows else {}
        except Exception as exc:
            raise DatabaseOperationError(f"新增 {table} 失败：{exc}") from exc

    def update(self, table: str, row_id: str, record: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.client.table(table).update(clean_record(record)).eq("id", row_id).execute()
            rows = list(response.data or [])
            return rows[0] if rows else {}
        except Exception as exc:
            raise DatabaseOperationError(f"更新 {table} 失败：{exc}") from exc

    def delete(self, table: str, row_id: str) -> None:
        try:
            self.client.table(table).delete().eq("id", row_id).execute()
        except Exception as exc:
            raise DatabaseOperationError(f"删除 {table} 失败：{exc}") from exc

    def upsert_many(
        self,
        table: str,
        records: Iterable[dict[str, Any]],
        *,
        on_conflict: str,
        batch_size: int = 200,
    ) -> int:
        cleaned = [clean_record(record) for record in records]
        if not cleaned:
            return 0
        total = 0
        try:
            for start in range(0, len(cleaned), batch_size):
                batch = cleaned[start : start + batch_size]
                response = self.client.table(table).upsert(batch, on_conflict=on_conflict).execute()
                total += len(response.data or batch)
            return total
        except Exception as exc:
            raise DatabaseOperationError(f"批量写入 {table} 失败：{exc}") from exc

    def upload_bytes(self, bucket: str, path: str, payload: bytes, content_type: str) -> None:
        try:
            self.client.storage.from_(bucket).upload(
                path,
                payload,
                {"content-type": content_type, "upsert": "true"},
            )
        except Exception as exc:
            raise DatabaseOperationError(f"上传原始文件失败：{exc}") from exc


def get_repository() -> SupabaseRepository | None:
    settings = get_supabase_settings()
    if not settings.configured:
        return None
    return SupabaseRepository(_build_client(settings.url, settings.key), settings)
