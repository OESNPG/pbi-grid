import argparse
import sys
from pathlib import Path

from .grid.schema import LayoutSpec
from .grid.engine import build
from .grid.renderer import render
from .grid.extractor import extract
from .grid.scaffold import scaffold


def _cmd_generate(args: argparse.Namespace) -> None:
    layout_path = Path(args.layout)
    if not layout_path.exists():
        print(f"Error: layout file not found: {layout_path}", file=sys.stderr)
        sys.exit(1)

    layout = LayoutSpec.from_yaml(layout_path)
    report = build(layout, debug=args.debug)

    output = Path(args.output) if args.output else layout_path.parent
    report_dir = render(report, output, source_report_path=layout.source_report_path)
    print(f"Generated: {report_dir}")


def _cmd_extract(args: argparse.Namespace) -> None:
    report_path = Path(args.report)
    if not report_path.exists():
        print(f"Error: report folder not found: {report_path}", file=sys.stderr)
        sys.exit(1)

    output = Path(args.output) if args.output else None
    merge_with = Path(args.merge) if args.merge else None
    if merge_with and not merge_with.exists():
        print(f"Error: --merge file not found: {merge_with}", file=sys.stderr)
        sys.exit(1)

    layout_path = extract(report_path, output, merge_with=merge_with)
    action = "Merged" if merge_with else "Extracted"
    print(f"{action}: {layout_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pbi-grid",
        description="Generate Power BI PBIR reports from a declarative layout YAML.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Generate PBIR from a layout YAML file.")
    gen.add_argument("--layout", required=True, metavar="FILE",
                     help="Path to the layout YAML file.")
    gen.add_argument("--output", default=None, metavar="DIR",
                     help="Output directory (default: same directory as the layout file).")
    gen.add_argument("--debug-grid", action="store_true", dest="debug",
                     help="Overlay semi-transparent grid cell outlines on every page.")

    ext = sub.add_parser("extract", help="Extract a layout YAML from an existing .Report folder.")
    ext.add_argument("--report", required=True, metavar="DIR",
                     help="Path to the .Report folder.")
    ext.add_argument("--output", default=None, metavar="FILE",
                     help="Output YAML file (default: <report_dir>/<ReportName>_layout.yaml).")
    ext.add_argument("--merge", default=None, metavar="FILE",
                     help="Existing layout YAML to merge into. Pages already present are "
                          "preserved verbatim (component/menu configs kept); only new pages "
                          "are extracted from the report.")

    scf = sub.add_parser("scaffold", help="Interactively add a component to a layout YAML.")
    scf.add_argument("--layout", required=True, metavar="FILE",
                     help="Path to the layout YAML file to modify.")

    args = parser.parse_args()

    if args.command == "generate":
        _cmd_generate(args)
    elif args.command == "extract":
        _cmd_extract(args)
    elif args.command == "scaffold":
        scaffold(Path(args.layout))


if __name__ == "__main__":
    main()
