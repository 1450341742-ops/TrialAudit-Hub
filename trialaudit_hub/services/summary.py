from __future__ import annotations

from datetime import date

import pandas as pd

from .io import DataBundle
from .metrics import calculate_kpis, flow_with_status, monthly_plan_actual, staff_load
from .quality import build_quality_report


def generate_management_summary(
    bundle: DataBundle,
    annual_target: int = 300,
    year: int = 2026,
    month: int | None = None,
    today: date | None = None,
) -> str:
    month = month or (today or date.today()).month
    kpi = calculate_kpis(
        bundle.projects,
        bundle.flows,
        bundle.targets,
        bundle.parttime,
        annual_target,
        year,
        month,
        today,
    )
    monthly = monthly_plan_actual(bundle.projects, bundle.targets, year)
    current = monthly.loc[monthly["month"].eq(month)].iloc[0]
    flow = flow_with_status(bundle.flows, today)
    load = staff_load(bundle.projects)
    quality = build_quality_report(bundle.projects, bundle.flows, bundle.parttime)
    high_load = (
        load[(load["month"] == month) & load["load_level"].isin(["关注", "高负荷"])]
        if not load.empty
        else pd.DataFrame()
    )
    top_people = "、".join(high_load.head(5)["person"].tolist()) or "暂无"
    overdue_ids = (
        "、".join(
            flow.loc[flow.get("report_overdue_days", 0).gt(0), "project_no"].astype(str).head(5).tolist()
        )
        if not flow.empty
        else ""
    ) or "暂无"
    gap = int(current["actual"] - current["plan"])
    gap_text = f"超额{gap}院次" if gap > 0 else (f"少于计划{abs(gap)}院次" if gap < 0 else "与计划一致")
    return (
        f"【{year}年{month}月项目运营分析】\n"
        f"1. 交付结果：本月计划{int(current['plan'])}院次，实际完成{int(current['actual'])}院次，{gap_text}；"
        f"年度累计完成{kpi.completed}院次，年度目标{kpi.annual_target}院次，完成率{kpi.annual_rate:.1%}。\n"
        f"2. 流程风险：待报告{kpi.pending_reports}项，报告逾期{kpi.overdue_reports}项，待CAPA{kpi.pending_capa}项。"
        f"报告逾期项目示例：{overdue_ids}。\n"
        f"3. 人员资源：本月高负荷人员{kpi.high_load_people}人；关注或高负荷人员：{top_people}。\n"
        f"4. 兼职投入：本月兼职费用合计{kpi.parttime_cost:,.0f}元。\n"
        f"5. 数据质量：当前识别{len(quality)}条异常或待确认事项。空白字段仅代表系统未记录，需由责任人确认。\n"
        "6. 建议动作：优先处理逾期报告和CAPA；复核高负荷人员后续排班；完成项目分期、日期和费用备注的标准化确认。"
    )
