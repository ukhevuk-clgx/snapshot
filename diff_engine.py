import gzip
import json
from pathlib import Path
from urllib.parse import urlsplit

from utils.datetime_utils import iso_timestamp


RELATION_KEYS = {
    "workflowSchemeMappings": ("workflowSchemeId", "issueTypeId"),
    "issueTypeSchemeMappings": ("issueTypeSchemeId", "issueTypeId"),
    "fieldConfigurationSchemeMappings": ("fieldConfigurationSchemeId", "issueTypeId"),
    "workItemSecurityLevels": ("schemeId", "levelId"),
    "permissionSchemeGrants": ("permissionSchemeId", "grantId"),
    "notificationSchemeEvents": ("notificationSchemeId", "eventId", "notificationId"),
    "projectPermissionSchemeMappings": ("projectId",),
    "projectNotificationSchemeMappings": ("projectId",),
    "projectSecuritySchemeMappings": ("projectId",),
}
PROJECT_RELATIONS = {
    "projectPermissionSchemeMappings", "projectNotificationSchemeMappings",
    "projectSecuritySchemeMappings",
}


def load_snapshot(path):
    path = Path(path)
    opener = gzip.open if path.suffix.lower() == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        snapshot = json.load(stream)
    validate_snapshot(snapshot)
    return snapshot


def validate_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        raise ValueError("Snapshot must be a JSON object")
    for section in ("metadata", "data", "relations"):
        if not isinstance(snapshot.get(section), dict):
            raise ValueError(f"Snapshot requires an object section: {section}")
    site = snapshot["metadata"].get("site")
    if not isinstance(site, str) or not site.strip():
        raise ValueError("Snapshot metadata.site is required")
    parsed = urlsplit(site)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Snapshot metadata.site must be an HTTP(S) URL")
    capabilities = snapshot["metadata"].get("capabilities", {})
    if not isinstance(capabilities, dict):
        raise ValueError("Snapshot metadata.capabilities must be an object")
    for section in ("data", "relations"):
        for name, rows in snapshot[section].items():
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise ValueError(f"{section}.{name} must be a list of objects")


def _site(snapshot):
    site = urlsplit(snapshot["metadata"]["site"].strip())
    return site.scheme.lower(), site.netloc.lower(), site.path.rstrip("/")


def _id(value, label, nullable=False):
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int)) or str(value) == "":
        raise ValueError(f"Missing or invalid identifier: {label}")
    return str(value)


def _identity(section, name, row):
    if section == "data":
        value = row.get("id")
        if name == "workflows" and isinstance(value, dict):
            entity_id = value.get("entityId")
            if entity_id is not None:
                return {"id": _id(entity_id, "workflows.id.entityId")}
            # Jira's legacy workflow identity can contain only its name and draft flag.
            workflow_name = value.get("name")
            if not isinstance(workflow_name, str) or not workflow_name:
                raise ValueError("Workflow identity requires entityId or name")
            draft = value.get("draft", False)
            if not isinstance(draft, bool):
                raise ValueError("Workflow identity draft must be a boolean")
            return {"name": workflow_name, "draft": draft}
        return {"id": _id(value, f"{name}.id")}
    if name not in RELATION_KEYS:
        raise ValueError(f"Unsupported relation collection: {name}")
    identity = {}
    for field in RELATION_KEYS[name]:
        if field not in row:
            raise ValueError(f"Missing relation identity field: {name}.{field}")
        identity[field] = _id(row[field], f"{name}.{field}",
                              nullable=name == "workflowSchemeMappings" and field == "issueTypeId")
    return identity


def _normalized(value, field=""):
    if isinstance(value, dict):
        return {key: _normalized(item, key) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalized(item) for item in value]
    if (field == "id" or field.endswith("Id")) and isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return value


def _index(section, name, rows):
    result = {}
    for row in rows:
        identity = _identity(section, name, row)
        key = json.dumps(identity, sort_keys=True)
        if key in result:
            raise ValueError(f"Duplicate identity in {section}.{name}: {key}")
        result[key] = (identity, row)
    return result


def _compare(section, name, before, after):
    a, b = _index(section, name, before), _index(section, name, after)
    result = {"added": [], "removed": [], "changed": []}
    for key in sorted(b.keys() - a.keys()):
        identity, row = b[key]
        result["added"].append({"identity": identity, "object": row})
    for key in sorted(a.keys() - b.keys()):
        identity, row = a[key]
        result["removed"].append({"identity": identity, "object": row})
    for key in sorted(a.keys() & b.keys()):
        identity, old = a[key]
        new = b[key][1]
        fields = {}
        for field in sorted(old.keys() | new.keys()):
            old_present, new_present = field in old, field in new
            old_value = json.dumps(_normalized(old.get(field), field), sort_keys=True)
            new_value = json.dumps(_normalized(new.get(field), field), sort_keys=True)
            if old_present != new_present or old_value != new_value:
                fields[field] = {
                    "beforePresent": old_present, "afterPresent": new_present,
                    "before": old.get(field), "after": new.get(field),
                }
        if fields:
            result["changed"].append({
                "identity": identity, "before": old, "after": new, "fields": fields,
            })
    return result


def compare_snapshots(before, after):
    validate_snapshot(before)
    validate_snapshot(after)
    if _site(before) != _site(after):
        raise ValueError("ID-based comparison requires snapshots from the same Jira site")
    report = {
        "metadata": {
            "diffVersion": "1", "created": iso_timestamp(), "site": before["metadata"]["site"],
            "matching": "id", "snapshotA": before["metadata"], "snapshotB": after["metadata"],
        },
        "warnings": [],
        "summary": {"objects": {}, "relations": {}},
        "totals": {
            "objects": {"added": 0, "removed": 0, "changed": 0},
            "relations": {"added": 0, "removed": 0, "changed": 0},
        },
        "objects": {}, "relations": {},
    }
    warnings = report["warnings"]
    if before["metadata"].get("snapshotVersion") != after["metadata"].get("snapshotVersion"):
        warnings.append("Snapshot versions differ; schema changes may appear as changed fields.")
    archived_ids = {
        _id(row.get("id"), "projects.id")
        for snapshot in (before, after)
        for row in snapshot["data"].get("projects", []) if row.get("archived")
    }
    for source, target in (("data", "objects"), ("relations", "relations")):
        for name in sorted(before[source].keys() | after[source].keys()):
            reason = None
            if name not in before[source] or name not in after[source]:
                reason = "collection is missing from one snapshot"
            elif source == "data" and name == "fieldSchemes" and any(
                snapshot["metadata"].get("capabilities", {}).get("fieldSchemesApi") is not True
                for snapshot in (before, after)
            ):
                reason = "Field Schemes API availability is not confirmed in both snapshots"
            if reason:
                warnings.append(f"Skipped {source}.{name}: {reason}.")
                report["summary"][target][name] = {"status": "skipped", "reason": reason}
                continue
            old, new = before[source][name], after[source][name]
            if source == "relations" and name in PROJECT_RELATIONS and archived_ids:
                old = [row for row in old if _id(row.get("projectId"), f"{name}.projectId") not in archived_ids]
                new = [row for row in new if _id(row.get("projectId"), f"{name}.projectId") not in archived_ids]
                warnings.append(f"{name}: excluded mappings for projects archived in either snapshot; these are not evidence of removal.")
            if source == "data" and name == "workflows" and any(
                isinstance(row.get("id"), dict) and row["id"].get("entityId") is None
                for row in old + new
            ):
                warnings.append("Legacy workflows without entityId are matched by identity name/draft; a rename may appear as added/removed.")
            changes = _compare(source, name, old, new)
            report[target][name] = changes
            counts = {kind: len(rows) for kind, rows in changes.items()}
            report["summary"][target][name] = {"status": "compared", **counts}
            for kind, count in counts.items():
                report["totals"][target][kind] += count
    warnings.append("Only collected snapshot fields are compared. Added/removed records are not automatic cleanup recommendations; visibility or permissions may also change.")
    return report
