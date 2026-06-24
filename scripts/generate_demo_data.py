"""Generate two synthetic workbooks for local TrialAudit Hub demonstrations."""
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "demo_data"
OUT.mkdir(exist_ok=True)

projects = pd.DataFrame(
    [
        [1, "DEMO-001", "Protocol-A", "示例中心A", "内资", "III期", "肺癌", 1, "示例稽查员A、示例稽查员B", 5, "1月4日-6日"],
        [2, "DEMO-002", "Protocol-B", "示例中心B", "外资", "I期", "CAR-T", 1, "示例稽查员A", 2, "2月10日-12日"],
    ],
    columns=["序号", "项目编号", "申办方项目编号", "中心名称", "申办方", "分期", "项目类型", "数量", "参与稽查的老师", "例数", "稽查时间"],
)
summary = pd.DataFrame([
    ["一月", "第1周", "第2周", "第3周", "第4周", "总院次"],
    ["计划院此", 1, 0, 0, 0, 1],
    ["实际院此", 1, 0, 0, 0, 1],
    ["达成率", 1, None, None, None, 1],
    ["二月", "第1周", "第2周", "第3周", "第4周", "总院次"],
    ["计划院此", 0, 1, 0, 0, 1],
    ["实际院此", 0, 1, 0, 0, 1],
    ["达成率", None, 1, None, None, 1],
])
parttime = pd.DataFrame([["1月"], ["姓名", "天数", "项目时间", "单价", "总价"], ["示例兼职", 2, "1月4日-5日", 500, 1000]])
with pd.ExcelWriter(OUT / "weekly_demo.xlsx", engine="openpyxl") as writer:
    summary.to_excel(writer, sheet_name="1、项目总体汇报", index=False, header=False)
    projects.to_excel(writer, sheet_name="4、2026项目原始数据", index=False)
    parttime.to_excel(writer, sheet_name="兼职稽查员统计", index=False, header=False)

flows = projects.copy()
flows["启动函"] = "已发送"
flows["资料"] = "收到"
flows["是否创建钉盘"] = "已确认"
flows["报告预计回复报告时间"] = pd.to_datetime(["2026-01-20", "2026-02-25"])
flows["报告跟踪情况"] = ["定稿", "跟踪报告"]
flows["CAPA预计回复报告时间"] = [None, None]
flows["CAPA跟踪情况"] = ["结束", None]
flows["是否定稿"] = ["全部定稿", None]
with pd.ExcelWriter(OUT / "flow_demo.xlsx", engine="openpyxl") as writer:
    flows.to_excel(writer, sheet_name="稽查流程管理2026", index=False)

print(f"Demo files created in {OUT}")
