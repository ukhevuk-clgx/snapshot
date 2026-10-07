import argparse
import json
import re
import tempfile
from collections import defaultdict
from pathlib import Path

from xlsxwriter.exceptions import XlsxWriterException

from diff_engine import load_snapshot, validate_snapshot
from output.advisor_excel_exporter import export_advice_excel
from output.json_exporter import export_json
from utils.datetime_utils import file_timestamp
from utils.logger import Logger


REVIEW_ONLY = "Review manually; this report never performs cleanup or recommends automatic deletion."
STAGE7_SNAPSHOT_VERSION = "6"
REQUIRED_COLLECTIONS = (
    "customFields", "fieldUsage", "statuses", "priorities", "workflows",
    "workflowSchemes", "screens", "screenSchemes",
)
REQUIRED_RELATIONS = (
    "workflowSchemeMappings", "permissionSchemeGrants", "projectPermissionSchemeMappings",
)


def _normalized(value):
    return re.sub(r"\s+", " ", value.strip()).casefold() if isinstance(value, str) else ""


def _rows(snapshot, section, name):
    value = snapshot.get(section, {}).get(name, [])
    return value if isinstance(value, list) else []


def _advice(kind, severity, confidence, title, target, evidence, limitations, steps):
    return {
        "id": f"{kind}:{target}",
        "category": kind,
        "severity": severity,
        "confidence": confidence,
        "title": title,
        "target": target,
        "action": "review_only",
        "recommendation": REVIEW_ONLY,
        "evidence": evidence,
        "limitations": limitations,
        "recommendedNextSteps": steps,
    }


def _duplicate_groups(rows, key_fn):
    groups = defaultdict(list)
    for row in rows:
        key = key_fn(row)
        if key is not None:
            groups[key].append(row)
    return [sorted(group, key=lambda row: str(row.get("id", "")))
            for key, group in sorted(groups.items(), key=lambda item: repr(item[0])) if len(group) > 1]


def _coverage(snapshot):
    metadata = snapshot["metadata"]
    stage7 = str(metadata.get("snapshotVersion", "")) == STAGE7_SNAPSHOT_VERSION
    coverage = metadata.get("coverage", {})
    if not isinstance(coverage, dict):
        coverage = {}
    usage_coverage = coverage.get("customFieldUsage")
    if not isinstance(usage_coverage, dict):
        usage_coverage = {
            "status": "insufficient",
            "reason": "Snapshot has no valid custom field usage coverage metadata.",
        }
    known = {
        name: name in snapshot.get("data", {})
        for name in REQUIRED_COLLECTIONS
    }
    result = {
        "snapshotVersion": metadata.get("snapshotVersion"),
        "stage7Snapshot": stage7,
        "collections": {
            name: {
                "present": present,
                "status": "available" if stage7 and present else "insufficient_legacy_snapshot" if present else "missing",
                "recordCount": len(_rows(snapshot, "data", name)),
            }
            for name, present in known.items()
        },
        "relations": {
            name: {
                "present": name in snapshot.get("relations", {}),
                "status": (
                    "available" if stage7 and name in snapshot.get("relations", {})
                    else "insufficient_legacy_snapshot" if name in snapshot.get("relations", {})
                    else "missing"
                ),
                "recordCount": len(_rows(snapshot, "relations", name)),
            }
            for name in REQUIRED_RELATIONS
        },
        "customFieldUsage": usage_coverage,
        "screenReferences": coverage.get(
            "screenReferences",
            {"status": "insufficient", "reason": "Snapshot does not document screen-reference coverage."},
        ),
        "workflowScreenReferences": coverage.get(
            "workflowScreenReferences",
            {"status": "insufficient", "reason": "Snapshot does not document workflow transition screen coverage."},
        ),
        "globalLimitations": [
            "Snapshot visibility is limited by the Jira account's permissions and API coverage.",
            "JQL filters, automation rules, apps, integrations, field contexts, drafts, and team-managed project configuration may create dependencies not represented here.",
        ],
    }
    if not stage7:
        result["globalLimitations"].append(
            "Legacy/pre-Stage-7 snapshots are explicitly insufficient for usage and orphan analysis; missing evidence is not treated as proof of non-use."
        )
        result["customFieldUsage"] = {**result["customFieldUsage"], "status": "insufficient"}
    return result


def advise_cleanup(snapshot):
    validate_snapshot(snapshot)
    site = snapshot["metadata"].get("site")
    if not isinstance(site, str) or not site.strip():
        raise ValueError("Snapshot metadata.site is required")

    coverage = _coverage(snapshot)
    recommendations = []

    # Same-name statuses are meaningful only within an identical scope and category.
    def status_key(row):
        name = _normalized(row.get("name"))
        scope = _normalized(row.get("scopeType"))
        category = _normalized(row.get("statusCategoryKey") or row.get("statusCategoryName"))
        if not name or not scope or not category:
            return None
        project = str(row.get("scopeProjectId") or "") if scope == "project" else ""
        if scope == "project" and not project:
            return None
        return name, scope, project, category

    for group in _duplicate_groups(_rows(snapshot, "data", "statuses"), status_key):
        recommendations.append(_advice(
            "duplicate_status_candidate", "medium", "medium",
            f"Statuses share a name, scope, and category: {group[0].get('name')}",
            ",".join(str(row.get("id")) for row in group),
            {"statuses": group, "comparison": "normalized name + scope/project + status category"},
            ["Identical labels do not prove interchangeable workflow semantics; statuses can be referenced by workflows and issues."],
            ["Check workflow transitions, issue history, and project scope with administrators before considering consolidation."],
        ))

    for group in _duplicate_groups(
        _rows(snapshot, "data", "priorities"),
        lambda row: _normalized(row.get("name")) or None,
    ):
        recommendations.append(_advice(
            "duplicate_priority_candidate", "low", "medium",
            f"Priorities share a normalized name: {group[0].get('name')}",
            ",".join(str(row.get("id")) for row in group),
            {"priorities": group, "comparison": "case- and whitespace-insensitive name"},
            ["Priorities may differ in workflow, project, reporting, or integration usage even when labels match."],
            ["Review project usage, issue data, filters, automation, and integrations before deciding whether to standardize."],
        ))

    usage_status = coverage["customFieldUsage"].get("status")
    if coverage["stage7Snapshot"] and usage_status in ("available", "partial"):
        usage_rows = _rows(snapshot, "data", "fieldUsage")
        by_id = {str(row.get("fieldId")): row for row in usage_rows if row.get("fieldId") is not None}
        for field in sorted(_rows(snapshot, "data", "customFields"), key=lambda row: str(row.get("id", ""))):
            field_id = field.get("id")
            evidence = by_id.get(str(field_id), {})
            counts = [evidence.get(key) for key in ("screensCount", "contextsCount", "projectsCount")]
            if (
                evidence.get("lastUsedType") == "NOT_TRACKED"
                and all(type(value) is int and value == 0 for value in counts)
                and field.get("isLocked") is False
                and field.get("isManaged") is False
            ):
                recommendations.append(_advice(
                    "custom_field_review_candidate", "low", "low",
                    f"Custom field has no reported contexts, screens, or projects: {field.get('name')}",
                    str(field_id),
                    {"field": field, "usage": evidence},
                    [
                        "NOT_TRACKED means Jira has no last-used signal; it does not mean the field has never been used.",
                        "The API counts do not cover JQL filters, automation, apps, integrations, issue history, or every project type.",
                    ],
                    ["Check field contexts and issue values, saved filters/JQL, automation, apps, integrations, and project configuration with owners."],
                ))

    stage7 = coverage["stage7Snapshot"]
    workflows = _rows(snapshot, "data", "workflows")
    scheme_mappings = _rows(snapshot, "relations", "workflowSchemeMappings")
    referenced_workflow_names = {
        _normalized(row.get("workflowName")) for row in scheme_mappings if row.get("workflowName")
    }
    if (
        stage7
        and coverage["collections"]["workflowSchemes"]["present"]
        and "workflowSchemeMappings" in snapshot["relations"]
    ):
        for workflow in sorted(workflows, key=lambda row: str(row.get("name", "")).casefold()):
            name = workflow.get("name")
            if (
                workflow.get("isActive") is False
                and _normalized(name)
                and _normalized(name) not in referenced_workflow_names
            ):
                recommendations.append(_advice(
                    "workflow_review_candidate", "low", "low",
                    f"Workflow is inactive and not referenced by collected workflow schemes: {name}",
                    str((workflow.get("id") or {}).get("entityId") if isinstance(workflow.get("id"), dict) else workflow.get("id")),
                    {"workflow": workflow, "matchingSchemeMappings": []},
                    ["Workflow-scheme mappings do not establish all project usage; team-managed workflows, drafts, and permission-limited configuration can be absent."],
                    ["Verify project type, workflow drafts, workflow scheme associations, and administrator ownership before considering any change."],
                ))

    if (
        stage7
        and coverage["collections"]["screens"]["present"]
        and coverage["collections"]["screenSchemes"]["present"]
        and isinstance(coverage["screenReferences"], dict)
        and coverage["screenReferences"].get("status") in ("available", "partial", "best_effort")
    ):
        referenced_screen_ids = set()
        screen_columns = ("defaultScreenId", "createScreenId", "editScreenId", "viewScreenId")
        for scheme in _rows(snapshot, "data", "screenSchemes"):
            referenced_screen_ids.update(str(scheme[key]) for key in screen_columns if scheme.get(key) is not None)
        for workflow in workflows:
            refs = workflow.get("transitionScreenIds", [])
            if isinstance(refs, list):
                referenced_screen_ids.update(str(value) for value in refs)
        for screen in sorted(_rows(snapshot, "data", "screens"), key=lambda row: str(row.get("id", ""))):
            screen_id = screen.get("id")
            if screen_id is not None and str(screen_id) not in referenced_screen_ids:
                recommendations.append(_advice(
                    "screen_review_candidate", "low", "low",
                    f"Screen has no reference in collected screen schemes or workflow transitions: {screen.get('name')}",
                    str(screen_id),
                    {"screen": screen, "referenceSourcesChecked": ["screen schemes", "collected workflow transition screen identifiers"]},
                    [
                        "Screen-reference coverage is partial; issue-type screen-scheme assignments, team-managed projects, app-managed workflows, drafts, or hidden references may not be represented.",
                        "No observed reference is not proof that a screen is orphaned.",
                    ],
                    ["Inspect issue-type screen schemes, project screen assignments, workflow transition configuration, apps, and project owners before any change."],
                ))

    project_by_permission_scheme = defaultdict(list)
    for row in _rows(snapshot, "relations", "projectPermissionSchemeMappings"):
        if row.get("permissionSchemeId") is not None:
            project_by_permission_scheme[str(row["permissionSchemeId"])].append({
                "projectId": row.get("projectId"), "projectKey": row.get("projectKey"),
                "projectName": row.get("projectName"), "archived": row.get("projectArchived"),
            })
    for grant in _rows(snapshot, "relations", "permissionSchemeGrants"):
        holder_type = _normalized(grant.get("holderType"))
        permission = _normalized(grant.get("permission"))
        holder_name = _normalized(grant.get("holderParameter") or grant.get("holderValue"))
        kind = None
        severity = "medium"
        confidence = "medium"
        if holder_type in ("anyone", "anonymous", "public"):
            kind = "anonymous_permission_grant"
            severity = "high" if permission in ("browse_projects", "browse_project") else "medium"
            confidence = "high"
        elif holder_type == "group" and holder_name in (
            "jira-users", "jira-software-users", "jira-servicedesk-users", "jira-work-users",
        ):
            kind = "broad_authenticated_group_grant"
        if kind:
            scheme_id = grant.get("permissionSchemeId")
            grant_target = grant.get("grantId")
            if grant_target is None:
                grant_target = ":".join(str(value or "") for value in (
                    scheme_id, grant.get("permission"), grant.get("holderType"),
                    grant.get("holderParameter"), grant.get("holderValue"),
                ))
            recommendations.append(_advice(
                kind, severity, confidence,
                f"Permission scheme grant targets {'anonymous/public access' if kind == 'anonymous_permission_grant' else 'a broad Jira user group'}",
                str(grant_target),
                {
                    "grant": grant,
                    "projectsUsingScheme": sorted(
                        project_by_permission_scheme.get(str(scheme_id), []),
                        key=lambda row: str(row.get("projectKey") or ""),
                    ),
                    "projectAssignmentEvidence": (
                        "matching project mapping observed"
                        if project_by_permission_scheme.get(str(scheme_id))
                        else "unknown; no matching mapping was observed"
                    ),
                },
                [
                    "A configured scheme grant is not proof that a user can access project data; project assignment, other grants, and product access affect effective permissions.",
                    "Project-to-scheme mappings may omit archived projects or mappings hidden by API permissions/errors.",
                    "Broad authenticated groups do not imply anonymous access.",
                ],
                ["Review effective permissions and intended audience for each assigned project; verify public-access policy with project/security owners."],
            ))

    recommendations.sort(key=lambda row: (
        row["category"], row["target"], row["title"], row["id"],
    ))
    return {
        "metadata": {
            "advisorVersion": "7",
            "site": site,
            "snapshotVersion": snapshot["metadata"].get("snapshotVersion"),
            "snapshotCreated": snapshot["metadata"].get("created"),
            "mode": "offline_recommendations_only",
        },
        "summary": {
            "recommendationCount": len(recommendations),
            "byCategory": {
                category: sum(row["category"] == category for row in recommendations)
                for category in sorted({row["category"] for row in recommendations})
            },
            "bySeverity": {
                severity: sum(row["severity"] == severity for row in recommendations)
                for severity in ("high", "medium", "low")
                if any(row["severity"] == severity for row in recommendations)
            },
        },
        "coverage": coverage,
        "recommendations": recommendations,
        "disclaimer": REVIEW_ONLY,
    }


def main(argv=None):
    snapshot_dir = Path(__file__).parent / "snapshots"
    parser = argparse.ArgumentParser(description="Generate offline, review-only Jira cleanup advice.")
    parser.add_argument("snapshot", type=Path, nargs="?", help="Snapshot JSON to analyze; defaults to snapshots\\snapshot_b.json")
    parser.add_argument("--input", dest="input_snapshot", type=Path, help="Snapshot JSON to analyze (alternative to positional path)")
    parser.add_argument("--output-dir", type=Path, default=snapshot_dir)
    args = parser.parse_args(argv)
    if args.snapshot is not None and args.input_snapshot is not None:
        parser.error("Specify the snapshot either positionally or with --input, not both")
    source = args.input_snapshot or args.snapshot or snapshot_dir / "snapshot_b.json"
    try:
        report = advise_cleanup(load_snapshot(source))
    except (OSError, EOFError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    report["metadata"]["source"] = str(source.resolve())
    try:
        args.output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        parser.error(f"Unable to create advice output directory: {exc}")
    stamp = file_timestamp()
    json_path = args.output_dir / f"cleanup_advice_{stamp}.json"
    excel_path = args.output_dir / f"cleanup_advice_{stamp}.xlsx"
    if json_path.exists() or excel_path.exists():
        parser.error("Advice output already exists; use a different output directory or retry later")
    created_paths = []
    try:
        with tempfile.TemporaryDirectory(prefix=".cleanup-advice-", dir=args.output_dir) as staging:
            staged_json = Path(staging) / json_path.name
            staged_excel = Path(staging) / excel_path.name
            export_json(report, staged_json)
            export_advice_excel(report, staged_excel)
            staged_json.rename(json_path)
            created_paths.append(json_path)
            staged_excel.rename(excel_path)
            created_paths.append(excel_path)
    except (OSError, ValueError, XlsxWriterException) as exc:
        for path in created_paths:
            path.unlink(missing_ok=True)
        parser.error(f"Unable to write advice reports: {exc}")
    Logger.info(f"Cleanup advice: {report['summary']['recommendationCount']} review-only recommendations")
    Logger.info(f"Advice JSON: {json_path}")
    Logger.info(f"Advice Excel: {excel_path}")
    return report


if __name__ == "__main__":
    main()
