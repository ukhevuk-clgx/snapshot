from collectors.base import BaseCollector


class FieldUsageCollector(BaseCollector):
    entity_name = "custom field usage evidence"

    def collect(self, fields):
        self.start()
        rows = []
        for field in fields:
            rows.append({
                "fieldId": field.get("id"),
                "fieldName": field.get("name"),
                "lastUsedType": field.get("lastUsedType"),
                "lastUsedAt": field.get("lastUsedAt"),
                "screensCount": field.get("screensCount"),
                "contextsCount": field.get("contextsCount"),
                "projectsCount": field.get("projectsCount"),
                "isLocked": field.get("isLocked"),
                "isManaged": field.get("isManaged"),
            })
        self.done(rows)
        return rows

    @staticmethod
    def coverage(rows):
        tracked = sum(row.get("lastUsedType") == "TRACKED" for row in rows)
        untracked = sum(row.get("lastUsedType") == "NOT_TRACKED" for row in rows)
        unknown = len(rows) - tracked - untracked
        missing_counts = sum(
            any(type(row.get(key)) is not int or row[key] < 0
                for key in ("screensCount", "contextsCount", "projectsCount"))
            for row in rows
        )
        return {
            "status": "available" if rows and unknown == 0 and missing_counts == 0 else "partial" if rows else "unknown",
            "source": "Jira REST API v3 field search lastUsed and usage counts",
            "reportedFields": len(rows),
            "trackedFields": tracked,
            "untrackedFields": untracked,
            "unknownFields": unknown,
            "fieldsWithIncompleteCounts": missing_counts,
            "limitations": [
                "Last-used tracking may be unavailable for a field and does not cover JQL filters, automation, apps, integrations, or all field contexts.",
                "Usage counts are Jira-reported signals, not proof that a field is safe to remove.",
            ],
        }
