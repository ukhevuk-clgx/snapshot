import argparse
from pathlib import Path

from diff_engine import compare_snapshots, load_snapshot
from output.diff_excel_exporter import export_diff_excel
from output.json_exporter import export_json
from utils.datetime_utils import file_timestamp
from utils.logger import Logger


def main(argv=None):
    snapshot_dir = Path(__file__).parent / "snapshots"
    parser = argparse.ArgumentParser(description="Compare before/after Jira snapshots from the same site by ID.")
    parser.add_argument("snapshot_a", type=Path, nargs="?", help="Before migration: defaults to snapshots\\snapshot_a.json")
    parser.add_argument("snapshot_b", type=Path, nargs="?", help="After migration: defaults to snapshots\\snapshot_b.json")
    parser.add_argument("--output-dir", type=Path, default=snapshot_dir)
    args = parser.parse_args(argv)
    if (args.snapshot_a is None) != (args.snapshot_b is None):
        parser.error("Provide both snapshot paths, or omit both to use the default files")
    if args.snapshot_a is None:
        args.snapshot_a = snapshot_dir / "snapshot_a.json"
        args.snapshot_b = snapshot_dir / "snapshot_b.json"
    try:
        report = compare_snapshots(load_snapshot(args.snapshot_a), load_snapshot(args.snapshot_b))
    except (OSError, EOFError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    report["metadata"]["sourceA"] = str(args.snapshot_a.resolve())
    report["metadata"]["sourceB"] = str(args.snapshot_b.resolve())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = file_timestamp()
    json_path = args.output_dir / f"snapshot_diff_{stamp}.json"
    excel_path = args.output_dir / f"snapshot_diff_{stamp}.xlsx"
    if json_path.exists() or excel_path.exists():
        raise FileExistsError("Diff output already exists; use a different output directory or retry later")
    export_json(report, json_path)
    export_diff_excel(report, excel_path)
    for section, counts in report["totals"].items():
        Logger.info(f"{section}: Added={counts['added']}, Removed={counts['removed']}, Changed={counts['changed']}")
    for warning in report["warnings"]:
        Logger.warning(warning)
    Logger.info(f"Diff JSON: {json_path}")
    Logger.info(f"Diff Excel: {excel_path}")
    return report


if __name__ == "__main__":
    main()
