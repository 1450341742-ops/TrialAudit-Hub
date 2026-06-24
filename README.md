# TrialAudit Hub

临床稽查项目管理与运营分析平台。系统使用 Streamlit 构建前端，通过 Supabase Postgres 保存业务数据，并支持现有 Excel 一键清洗导入和人工维护。

## 当前功能

- Supabase 数据库连接与运行状态检查
- 项目台账：查询、新增、编辑、删除
- 流程管理：资料、钉盘、EDC、报告、CAPA、定稿和回款
- 人员排班：稽查员档案、每日排班、负荷和冲突统计
- 兼职费用：天数、单价、调整金额、实付和付款状态
- 目标管理：月度计划、实际、达成率和年度完成率
- 数据导入：解析两份现有 Excel，预览、质量检查、Upsert 写入数据库
- 原始 Excel 可选存档到 Supabase 私有 Storage
- 管理驾驶舱：院次、病例、目标、逾期、人员负荷和项目结构

## 数据安全

原始 Excel、Supabase URL 和密钥均不会提交到 GitHub。仓库已忽略 `*.xlsx`、`*.xls` 和 `.streamlit/secrets.toml`。数据库表已启用 RLS，当前内部版本使用仅存放在服务端 Secrets 中的 service-role 密钥访问。

## 初始化 Supabase

1. 创建 Supabase 项目。
2. 打开 Supabase Dashboard 的 SQL Editor。
3. 执行 [`supabase/schema.sql`](supabase/schema.sql)。
4. 复制 `.streamlit/secrets.toml.example` 为 `.streamlit/secrets.toml`，填写：

```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "YOUR_SERVICE_ROLE_KEY"
```

正式部署时，请在 Streamlit Community Cloud 的应用设置中配置同名 Secrets，不要把真实密钥提交到仓库。

## 本地运行

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Excel 导入

进入“数据导入”页面，上传：

1. 项目管理部每周汇报表；
2. 中心稽查项目流程记录表。

系统将按项目编号更新项目台账，并导入流程、排班、兼职和月度目标。导入过程采用 Upsert，相同项目编号和来源键不会重复新增。

## 页面结构

- 首页：经营驾驶舱
- 项目台账
- 流程管理
- 人员排班
- 兼职费用
- 目标管理
- 数据导入
- 系统设置

## 后续可扩展

- Supabase Auth 登录及按角色权限
- 钉钉待办和消息提醒
- 报告/CAPA 自动催办
- 多中心项目进度
- AI 周报、风险摘要和趋势预测
