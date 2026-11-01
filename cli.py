#!/usr/bin/env python3
"""Command-line entry for the quote normalizer.

Usage:
    python3 cli.py quotes.json            # human-readable table + unknowns
    python3 cli.py quotes.json --json     # full JSON result
    python3 cli.py quotes.json --trace    # include the arithmetic trace

Input file format: {"quotes": [ ... ]} with 2 to 5 quotes.
Exit codes: 0 success, 2 invalid input, 1 unexpected error.
"""

from __future__ import annotations

import json
import sys

from quote_norm import InvalidInput, normalize


def render(result: dict, show_trace: bool) -> str:
    lines = []
    lines.append(f"Quotes compared: {result['quote_count']}    Term: {result['term_months']} months")
    lines.append("")
    header = f"{'Supplier':<14}{'Currency':<10}{'Total':>12}{'Per month':>12}"
    lines.append(header)
    lines.append("-" * len(header))
    for quote in result["quotes"]:
        lines.append(
            f"{quote['supplier'][:13]:<14}"
            f"{str(quote['currency'] or '-'):<10}"
            f"{quote['total_term']:>12,.2f}"
            f"{quote['monthly_equivalent']:>12,.2f}"
        )
    lines.append("")
    if result.get("lowest_total"):
        lines.append(f"Lowest total: {result['lowest_total']}")
        lines.append("Ranking: " + " < ".join(result["ranking_by_total_term"]))
    else:
        lines.append("Lowest total: not determined (quotes use different currencies)")
        for currency, ranking in result.get("ranking_by_currency", {}).items():
            lines.append(f"  {currency}: " + " < ".join(ranking))

    unknowns = [(q["supplier"], u) for q in result["quotes"] for u in q["unknowns"]]
    if unknowns:
        lines.append("")
        lines.append("Unknowns (confirm with the supplier, not estimated):")
        for supplier, item in unknowns:
            lines.append(f"  - {supplier}: {item}")

    if result["warnings"]:
        lines.append("")
        lines.append("Comparability warnings:")
        for warning in result["warnings"]:
            lines.append(f"  - {warning}")

    if show_trace:
        lines.append("")
        lines.append("Arithmetic trace:")
        for quote in result["quotes"]:
            for step in quote["trace"]:
                lines.append(f"  {step}")

    return "\n".join(lines)


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    flags = {a for a in argv[1:] if a.startswith("--")}

    if not args:
        print(__doc__.strip())
        return 2

    path = args[0]
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        print(f"File not found: {path}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as error:
        print(f"Input is not valid JSON: {error}", file=sys.stderr)
        return 2

    quotes = payload.get("quotes") if isinstance(payload, dict) else payload

    try:
        result = normalize(quotes)
    except InvalidInput as error:
        print(f"Invalid input: {error}", file=sys.stderr)
        return 2

    if "--json" in flags:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render(result, show_trace="--trace" in flags))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
