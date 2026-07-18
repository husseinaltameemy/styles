"""Command-line interface for batch classification (no Streamlit needed).

Usage:
    python classify_cli.py INPUT.csv [-o OUTPUT.csv] [--report report.md]
    python classify_cli.py export.ris --report -      # report to stdout

Reads a CSV or RIS export, writes the enriched CSV, and optionally a Markdown
summary. Handy for pipelines and for sanity-checking the engine on real exports.
"""
from __future__ import annotations

import argparse
import sys

from classifier import loaders, pipeline, report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input", help="CSV or RIS export to classify")
    ap.add_argument("-o", "--output", default=None,
                    help="enriched CSV output path (default: INPUT.classified.csv)")
    ap.add_argument("--report", default=None,
                    help="Markdown report path, or '-' for stdout")
    args = ap.parse_args(argv)

    with open(args.input, "rb") as fh:
        data = fh.read()
    df = loaders.load(data, args.input)
    if len(df) == 0:
        print("No records found in input.", file=sys.stderr)
        return 1

    out = pipeline.classify_dataframe(df)
    out_path = args.output or (args.input.rsplit(".", 1)[0] + ".classified.csv")
    out.to_csv(out_path, index=False)
    mena = int(out["mena_relevant"].sum())
    print(f"Classified {len(out)} records -> {out_path}  "
          f"({mena} MENA-relevant, {mena / len(out):.0%})", file=sys.stderr)

    if args.report:
        md = report.build_report(out)
        if args.report == "-":
            print(md)
        else:
            with open(args.report, "w", encoding="utf-8") as fh:
                fh.write(md)
            print(f"Report -> {args.report}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
