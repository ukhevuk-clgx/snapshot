# Jira Snapshot Stage 7

## Credentials and publishing

`config.py` contains settings only, not credentials, and can be committed. Authentication is read from `JIRA_SITE`, `JIRA_EMAIL`, and `JIRA_TOKEN` environment variables, or from a local `.jira-credentials.json` next to `config.py`. Environment variables override local values individually. All three variables set in the environment bypass the local file entirely.

For local IDE runs, copy `.jira-credentials.example.json` to `.jira-credentials.json` and enter your credentials in the local copy only. This file is excluded by `.gitignore`, along with `.env` files, IDE configuration, and the contents of `snapshots`. Credentials remain plaintext locally: Git exclusion is not encryption. Keep the local file in a trusted location with restricted access; avoid syncing it through cloud storage if that is not permitted by your organization. Environment variables or an approved secret manager avoid keeping credentials in the project folder.

Never put real credentials in examples, source files, CLI arguments, logs, or commits. Use HTTPS for Jira. Offline comparison does not require credentials. For GitHub Actions, use GitHub Actions Secrets to populate environment variables rather than repository files.

Before publishing, inspect the exact staged files and diff, confirm local secret files and snapshots are not tracked, and check any existing Git history. `.gitignore` does not untrack files or erase credentials from past commits. A private repository is not a substitute for excluding secrets. Rotate any token previously shared or committed; removing it from source does not revoke it.

Adds Project Roles, Permission Schemes, Notification Schemes, permission grants, notification events, and project-to-governance-scheme dependencies. Archived projects remain in the project inventory, but their governance dependency requests are skipped.

Governance dependencies are collected for up to four active projects concurrently, using a separate reusable HTTP session per thread. Output preserves project order, and existing HTTP retry handling applies to each request. Set `GOVERNANCE_MAX_WORKERS` in `config.py` to a positive integer to adjust concurrency; use `1` for sequential collection. Jira rate limits may reduce the speedup.

## Snapshot Diff Engine

Keep the snapshot generated before migration, then run `snapshot.py` again after migration. Compare the JSON snapshots from the same Jira site, with the earlier snapshot first:

Snapshots are saved as readable UTF-8 `migration_snapshot_<timestamp>.json` files without compression.

```powershell
python .\compare_snapshots.py .\snapshots\before.json .\snapshots\after.json
```

Older `.json.gz` snapshots can still be read when supplied as explicit arguments. The comparison is offline and does not use Jira credentials or call Jira. Use `--output-dir .\snapshots\diff` to select the report directory.

To run without arguments (including using the IDE Run button), put `snapshot_a.json` (before) and `snapshot_b.json` (after) in the `snapshots` folder next to the script:

```powershell
python .\compare_snapshots.py
```

Default input paths are relative to the script, not the working directory. Explicit paths still work; provide both or neither.

The generated `snapshot_diff_<timestamp>.json` and `.xlsx` contain:

- **Added**: IDs present only in snapshot B, including new objects with existing names.
- **Removed**: IDs present only in snapshot A.
- **Changed**: matching IDs with changed fields, including before/after values and field presence.
- Separate object and relation summaries, with detailed changes to scheme mappings, grants, notification recipients, and project dependencies.

Record order and JSON object key order do not affect the diff. Numeric and string identifiers match; text fields are compared exactly. Workflows use `id.entityId` when provided by Jira; legacy workflow identities use name/draft with a warning. Duplicate or missing identities and different Jira sites are rejected rather than guessed.

Missing collections and field schemes without confirmed API availability in both snapshots are skipped with warnings, not reported as wholesale additions/removals. Governance mappings for projects archived in either snapshot are excluded from relation comparison because archive skipping does not prove that a mapping was removed.

Excel includes Summary, Metadata, Warnings, and separate Added/Removed/Changed sheets for objects and relations. Each changed field has its own Excel row; summary counts refer to objects/relations, not field rows. JSON preserves complete records; oversized Excel cells are truncated with an explicit pointer to JSON.

Only fields already collected by the snapshot are compared. Counts alone cannot detect changes to uncollected details. Keep collection permissions consistent: a disappearance can reflect API visibility rather than actual deletion. Added objects are review candidates, not automatic cleanup recommendations.

## Stage 7 Cleanup Advisor

Stage 7 snapshots use schema version `6` and capture Jira-reported custom-field last-used signals and context, screen, and project counts, plus transition screen references exposed by workflow search. These are evidence only: Jira may not track a field's usage, and filters/JQL, issue values, automation, apps, integrations, team-managed projects, and account permissions can hide dependencies. The new evidence reuses existing API responses and adds no extra requests. Snapshot diffs match field-usage records by `fieldId`.

Run the advisor against the after-migration snapshot (or another JSON snapshot) without Jira credentials or Jira API calls:

```powershell
python .\cleanup_advisor.py
python .\cleanup_advisor.py .\snapshots\migration_snapshot.json
python .\cleanup_advisor.py --input .\snapshots\migration_snapshot.json --output-dir .\snapshots\advice
```

With no input, `snapshots\snapshot_b.json` next to the script is used. The advisor writes UTF-8 `cleanup_advice_<timestamp>.json` and `.xlsx` reports. Legacy snapshots are labeled insufficient for usage and orphan analysis; missing collections or evidence are not treated as proof of non-use.

Recommendations identify review candidates for custom fields, duplicate statuses and priorities, inactive/unreferenced workflows, screens with no observed screen-scheme/workflow reference, and permission grants for anonymous/public or common broad authenticated groups. Status duplicates are compared within scope and category; same-name priorities and inactive workflows are candidates only, not presumed duplicates or unused. In particular, incomplete screen references, workflow drafts, project types, saved filters, apps, and effective permission assignments require administrator review.

The advisor is offline and read-only. It never deletes objects or recommends automatic deletion. Confirm dependencies, ownership, effective permissions, and operational impact with Jira/project administrators before making any configuration change.
