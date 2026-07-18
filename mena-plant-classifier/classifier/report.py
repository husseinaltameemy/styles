"""Markdown summary report of a classified corpus."""
from __future__ import annotations

import pandas as pd


def _counts(series: pd.Series, top: int | None = None) -> list[tuple[str, int]]:
    vc = series[series.astype(str).str.len() > 0].value_counts()
    items = list(vc.items())
    return items[:top] if top else items


def _explode_counts(series: pd.Series, top: int | None = None) -> list[tuple[str, int]]:
    """Count comma-separated multi-valued cells (plants, activities)."""
    tally: dict[str, int] = {}
    for cell in series.fillna("").astype(str):
        for item in (x.strip() for x in cell.split(",")):
            if item:
                tally[item] = tally.get(item, 0) + 1
    items = sorted(tally.items(), key=lambda kv: kv[1], reverse=True)
    return items[:top] if top else items


def build_report(df: pd.DataFrame) -> str:
    n = len(df)
    lines = ["# Medicinal-Plant Publication Classification — Summary", ""]
    lines.append(f"**Records analysed:** {n}")
    if n == 0:
        return "\n".join(lines)

    mena = int(df["mena_relevant"].sum())
    lines.append(f"**MENA-relevant records:** {mena} ({mena / n:.0%})")
    lines.append("")

    lines.append("## Publication types")
    for label, count in _counts(df["pub_type"]):
        lines.append(f"- {label}: {count} ({count / n:.0%})")
    lines.append("")

    lines.append("## Therapeutic activities (top 15)")
    for label, count in _explode_counts(df["activities"], top=15):
        lines.append(f"- {label}: {count}")
    lines.append("")

    lines.append("## Plants studied (top 20)")
    for label, count in _explode_counts(df["plants"], top=20):
        lines.append(f"- {label}: {count}")
    lines.append("")

    lines.append("## Countries")
    for label, count in _counts(df["country"], top=20):
        tag = " *(MENA)*" if _is_mena_row(df, label) else ""
        lines.append(f"- {label}: {count}{tag}")
    lines.append("")

    lines.append("## MENA basis")
    for label, count in _counts(df["mena_basis"]):
        pretty = {"country": "author country in MENA",
                  "plant": "MENA plant studied",
                  "country+plant": "both country and plant"}.get(label, label)
        lines.append(f"- {pretty}: {count}")
    lines.append("")
    lines.append("> Screening output — every label is derived from the supplied "
                 "text and reference vocabularies, and should be spot-checked "
                 "before use in a systematic review.")
    return "\n".join(lines)


def _is_mena_row(df: pd.DataFrame, country: str) -> bool:
    sub = df[df["country"] == country]
    return bool(len(sub) and sub["country_mena"].iloc[0])
