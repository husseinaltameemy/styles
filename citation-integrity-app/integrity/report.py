"""Generate a brief, human-readable integrity report from the analyses."""
from __future__ import annotations

from datetime import date


def _fmt_list(items: list[str], limit: int = 10) -> str:
    if not items:
        return "_none_"
    shown = items[:limit]
    extra = f" (+{len(items) - limit} more)" if len(items) > limit else ""
    return ", ".join(shown) + extra


def build_report(
    cartel: dict | None = None,
    selfcite: dict | None = None,
    coercion: dict | None = None,
    retraction: dict | None = None,
) -> str:
    """Assemble a Markdown brief summarizing all available findings."""
    lines: list[str] = []
    lines.append("# Citation & Editorial Integrity Report")
    lines.append(f"_Generated {date.today().isoformat()}_\n")

    # --- Executive summary ---------------------------------------------------
    flagged_overall: set[str] = set()
    if cartel:
        for c in cartel.get("clusters", []):
            flagged_overall.update(c["journals"].split(", "))
    if selfcite:
        flagged_overall.update(selfcite.get("flagged_high", []))
    if coercion:
        flagged_overall.update(coercion.get("flagged", []))
    if retraction:
        flagged_overall.update(retraction.get("flagged_editorial", []))

    lines.append("## Executive summary")
    if flagged_overall:
        lines.append(
            f"**{len(flagged_overall)} journal(s)** raised one or more integrity "
            f"flags: {_fmt_list(sorted(flagged_overall))}."
        )
    else:
        lines.append("No journals raised integrity flags in the supplied data.")
    lines.append("")

    # --- Citation cartels ----------------------------------------------------
    if cartel is not None:
        lines.append("## 1. Citation cartels")
        lines.append(
            f"Analyzed a citation graph of **{cartel['n_journals']} journals** "
            f"and **{cartel['n_edges']} directed edges**.\n"
        )
        pairs = cartel.get("reciprocal_pairs", [])
        if pairs:
            lines.append("**Top reciprocal (mutually-citing) pairs:**")
            lines.append("")
            lines.append("| Journal A | Journal B | A→B | B→A | Reciprocity |")
            lines.append("|---|---|---|---|---|")
            for p in pairs[:5]:
                lines.append(
                    f"| {p['journal_a']} | {p['journal_b']} | {p['a_to_b']:.0f} | "
                    f"{p['b_to_a']:.0f} | {p['reciprocity_score']} |"
                )
            lines.append("")
        clusters = cartel.get("clusters", [])
        if clusters:
            lines.append("**Suspected cartel clusters (high internal-citation ratio):**")
            lines.append("")
            for c in clusters[:5]:
                lines.append(
                    f"- {c['journals']} — internal ratio "
                    f"{c['internal_ratio']}, score {c['cartel_score']}"
                )
            lines.append("")
        if not pairs and not clusters:
            lines.append("No reciprocal pairs or cartel clusters detected.\n")

    # --- Self-citation -------------------------------------------------------
    if selfcite is not None:
        lines.append("## 2. Self-citation")
        high = selfcite.get("flagged_high", [])
        spike = selfcite.get("flagged_spike", [])
        lines.append(f"- High self-citation rate: {_fmt_list(high)}")
        lines.append(f"- Year-over-year self-citation spike: {_fmt_list(spike)}")
        table = selfcite.get("table")
        if table is not None and not table.empty:
            lines.append("")
            lines.append("**Highest self-citation rates:**")
            lines.append("")
            lines.append("| Journal | Self-cites | Received | Self-rate |")
            lines.append("|---|---|---|---|")
            for r in table.head(5).itertuples(index=False):
                lines.append(
                    f"| {r.journal} | {r.self_citations:.0f} | "
                    f"{r.received_total:.0f} | {r.self_rate:.2f} |"
                )
        lines.append("")

    # --- Coercion ------------------------------------------------------------
    if coercion is not None:
        lines.append("## 3. Coercive self-citation risk")
        if not coercion.get("has_author_data"):
            lines.append(
                "_Note: no `citing_author` column supplied, so the author-spread "
                "signal is unavailable; scores rely on level and trend only._"
            )
        flagged = coercion.get("flagged", [])
        lines.append(f"- Elevated coercion-risk journals: {_fmt_list(flagged)}")
        table = coercion.get("table")
        if table is not None and not table.empty:
            lines.append("")
            lines.append("| Journal | Level | Trend | Spread | Risk |")
            lines.append("|---|---|---|---|---|")
            for r in table.head(5).itertuples(index=False):
                lines.append(
                    f"| {r.journal} | {r.level_component} | {r.trend_component} | "
                    f"{r.spread_component} | {r.coercion_risk} |"
                )
        lines.append(
            "\n_These are statistical indicators, not proof of misconduct._"
        )
        lines.append("")

    # --- Retractions ---------------------------------------------------------
    if retraction is not None:
        lines.append("## 4. Editorial integrity (retractions)")
        breakdown = retraction.get("cause_breakdown", {})
        if breakdown:
            causes = ", ".join(f"{k}: {v}" for k, v in breakdown.items())
            lines.append(f"- Retraction causes observed: {causes}")
        flagged = retraction.get("flagged_editorial", [])
        lines.append(
            f"- Journals with editorial-process failures "
            f"(paper mill / faked peer review / fabrication): {_fmt_list(flagged)}"
        )
        scores = retraction.get("scores")
        if scores is not None and not scores.empty:
            lines.append("")
            lines.append("| Journal | Retractions | Editorial failures | Dominant cause | Risk |")
            lines.append("|---|---|---|---|---|")
            for r in scores.head(5).itertuples(index=False):
                lines.append(
                    f"| {r.journal} | {r.retractions} | {r.editorial_failures} | "
                    f"{r.dominant_cause} | {r.integrity_risk} |"
                )
        lines.append("")

    lines.append("---")
    lines.append(
        "_Generated by the Citation & Editorial Integrity app. Findings are "
        "screening indicators intended to guide further investigation, not "
        "conclusive evidence of misconduct._"
    )
    return "\n".join(lines)
