import json
from pathlib import Path

import pandas as pd

from output.excel_exporter import write


def _cell(value):
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if len(text) > 32767:
        return text[:32700] + "... [truncated; see JSON report]"
    return text


def export_diff_excel(report, path):
    summary = [
        {"Section": section, "Collection": name, **counts}
        for section, collections in report["summary"].items()
        for name, counts in collections.items()
    ]
    summary += [
        {"Section": section, "Collection": "TOTAL", **counts}
        for section, counts in report["totals"].items()
    ]
    metadata = [
        {"Property": key, "Value": _cell(value)}
        for key, value in report["metadata"].items()
    ]
    options = {"options": {"strings_to_formulas": False, "strings_to_urls": False}}
    with pd.ExcelWriter(Path(path), engine="xlsxwriter", engine_kwargs=options) as writer:
        write(writer, summary, "Summary")
        write(writer, metadata, "Metadata")
        write(writer, [{"Warning": text} for text in report["warnings"]], "Warnings")
        for section, label in (("objects", "Objects"), ("relations", "Relations")):
            for kind in ("added", "removed", "changed"):
                rows = []
                for name, changes in report[section].items():
                    for entry in changes[kind]:
                        base = {"Collection": name, "Identity": _cell(entry["identity"])}
                        if kind == "changed":
                            for field, values in entry["fields"].items():
                                rows.append({
                                    **base, "Name": entry["after"].get("name"),
                                    "Field": field, "Before Present": values["beforePresent"],
                                    "After Present": values["afterPresent"],
                                    "Before": _cell(values["before"]), "After": _cell(values["after"]),
                                })
                        else:
                            rows.append({
                                **base, "Name": entry["object"].get("name"),
                                "Object": _cell(entry["object"]),
                            })
                write(writer, rows, f"{label} {kind.title()}")
