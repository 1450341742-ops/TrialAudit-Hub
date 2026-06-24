# TrialAudit Hub

临床稽查项目管理与运营分析平台。当前版本为可运行的 Streamlit MVP，面向项目管理部每周汇报表与中心稽查项目流程记录表，支持上传后自动识别、跨表关联和运营看板分析。

## 已实现

- 项目院次、病例数和年度目标完成率
- 内外资、单多中心、分期和疾病领域结构分析
- 流程节点字段填写率与项目编号联动
- 稽查员月度行程负荷与高负荷提示
- 兼职稽查员投入趋势及费用测算
- 数据质量检查与明细导出
- 原Excel只读分析，不覆盖或修改源文件

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

## 使用方式

启动后在左侧分别上传：

1. 项目管理部每周汇报表；
2. 中心稽查项目流程记录表。

系统优先通过项目编号关联两份文件。由于历史Excel存在合并单元格、文本日期、空白字段及不同年份模板，页面中的流程完成率目前表示“字段填写率”，不直接等同于业务实际完成率。

## 部署到 Streamlit Community Cloud

- Main file path：`streamlit_app.py`
- Python version：3.11 或以上
- 无需配置数据库和密钥

## 下一阶段

- 精确解析月度计划与实际院次
- 项目状态和报告/CAPA逾期规则
- 多中心项目进度
- 用户登录和权限
- 数据库存储与历史版本
- AI周报和风险摘要
