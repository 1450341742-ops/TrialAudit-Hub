import pandas as pd

from app.importer import flow_projects_to_records, flows_to_records


def test_flow_status_is_derived_not_raw_note():
    flow = pd.DataFrame([
        {
            "项目编号": "P001",
            "中心名称": "测试中心",
            "稽查时间": "1月4日-7日",
            "报告跟踪情况": "跟踪报告",
            "项目状态": "2月2日邮件已催两回",
        }
    ])
    project = flow_projects_to_records(flow)[0]
    assert project["status"] == "待报告"
    detail = flows_to_records(flow, {"P001": "uuid-1"})[0]
    assert detail["status"] == "待报告"
    assert detail["notes"] == "2月2日邮件已催两回"
