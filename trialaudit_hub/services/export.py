from __future__ import annotations

from io import BytesIO

import pandas as pd

from .io import DataBundle
from .metrics import flow_with_status, monthly_plan_actual, node_completion, staff_load
from .quality import build_quality_report


def export_analysis(bundle: DataBundle, annual_target: int = 300, year: int = 2026) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        monthly_plan_actual(bundle.projects, bundle.targets, year).to_excel(
            writer,
            sheet_name="目标与实际",
            index=False,
        )
        bundle.projects.to_excel(writer, sheet_name="项目台账", index=False)
        flow_with_status(bundle.flows).to_excel(writer, sheet_name="流程分析", index=False)
        staff_load(bundle.projects).to_excel(writer, sheet_name="人员负荷", index=False)
        bundle.parttime.to_excel(writer, sheet_name="兼职费用", index=False)
        node_completion(bundle.flows).to_excel(writer, sheet_name="节点完成率", index=False)
        build_quality_report(bundle.projects, bundle.flows, bundle.parttime).to_excel(
            writer,
            sheet_name="数据质量",
            index=False,
        )
    return output.getvalue()
