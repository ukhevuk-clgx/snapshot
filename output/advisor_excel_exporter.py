import json
from pathlib import Path

import pandas as pd

from output.excel_exporter import write


def _cell(value):
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if len(text) > 32767:
        return text[:32700] + "... [truncated; see JSON report]"
    return text


def export_advice_excel(report, path):
    summary = [
        {"Metric": "Recommendation count", "Value": report["summary"]["recommendationCount"]},
        *[
            {"Metric": f"Category: {category}", "Value": count}
            for category, count in report["summary"]["byCategory"].items()
        ],
        *[
            {"Metric": f"Severity: {severity}", "Value": count}
            for severity, count in report["summary"]["bySeverity"].items()
        ],
    ]
    metadata = [{"Property": key, "Value": _cell(value)} for key, value in report["metadata"].items()]
    recommendations = [{
        "ID": row["id"],
        "Category": row["category"],
        "Severity": row["severity"],
        "Confidence": row["confidence"],
        "Title": row["title"],
        "Target": row["target"],
        "Action": row["action"],
        "Recommendation": row["recommendation"],
        "Evidence": _cell(row["evidence"]),
        "Limitations": _cell(row["limitations"]),
        "Recommended next steps": _cell(row["recommendedNextSteps"]),
    } for row in report["recommendations"]]
    options = {"options": {"strings_to_formulas": False, "strings_to_urls": False}}
    with pd.ExcelWriter(Path(path), engine="xlsxwriter", engine_kwargs=options) as writer:
        write(writer, summary, "Summary")
        write(writer, metadata, "Metadata")
        write(writer, [{"Area": key, "Coverage": _cell(value)} for key, value in report["coverage"].items()], "Coverage")
        write(writer, recommendations, "Recommendations")
        write(writer, [{"Disclaimer": report["disclaimer"]}], "Disclaimer")
