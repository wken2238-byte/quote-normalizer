"""Quote normalizer core: pure functions, no network, no I/O.

Purpose: turn 2-5 structured supplier quotes into comparable 12-month cost,
an arithmetic trace that a human can re-check, structural unknowns, and
comparability warnings. It never guesses a missing amount.
"""

from __future__ import annotations

from typing import Any

TERM_MONTHS = 12
PERIODS = {"monthly", "annual", "one_time"}


class InvalidInput(ValueError):
    """Raised when a quote cannot be computed at all."""


def _num(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidInput(f"{field} must be a number, got {value!r}")
    if value < 0:
        raise InvalidInput(f"{field} must not be negative, got {value!r}")
    return float(value)


def normalize_quote(quote: dict[str, Any], index: int) -> dict[str, Any]:
    label = quote.get("supplier") or f"quote_{index + 1}"
    prefix = f"quotes[{index}]"

    currency = quote.get("currency")
    period = quote.get("billing_period")
    if period not in PERIODS:
        raise InvalidInput(
            f"{prefix}.billing_period must be one of {sorted(PERIODS)}, got {period!r}"
        )

    unit_price = _num(quote.get("unit_price"), f"{prefix}.unit_price")
    quantity = _num(quote.get("quantity", 1), f"{prefix}.quantity")
    if quantity == 0:
        raise InvalidInput(f"{prefix}.quantity must be greater than 0")

    months = quote.get("commitment_months")
    if period == "monthly":
        if months is None:
            months = TERM_MONTHS
        months = int(_num(months, f"{prefix}.commitment_months"))
        if months <= 0:
            raise InvalidInput(f"{prefix}.commitment_months must be greater than 0")
    else:
        months = TERM_MONTHS

    fees = quote.get("fees") or []
    if not isinstance(fees, list):
        raise InvalidInput(f"{prefix}.fees must be a list")

    recurring = 0.0
    one_time = 0.0
    trace: list[str] = []

    line = unit_price * quantity
    if period == "monthly":
        recurring = line * months
        trace.append(f"{label}: {unit_price:g} x {quantity:g} per month x {months} months = {recurring:g}")
    elif period == "annual":
        recurring = line * (months / 12)
        trace.append(f"{label}: {unit_price:g} x {quantity:g} per year x {months / 12:g} year(s) = {recurring:g}")
    else:
        recurring = line
        trace.append(f"{label}: {unit_price:g} x {quantity:g} one-time = {recurring:g}")

    for fee_index, fee in enumerate(fees):
        if not isinstance(fee, dict):
            raise InvalidInput(f"{prefix}.fees[{fee_index}] must be an object")
        amount = _num(fee.get("amount"), f"{prefix}.fees[{fee_index}].amount")
        name = fee.get("label") or f"fee_{fee_index + 1}"
        if fee.get("recurring") is True:
            recurring += amount * months
            trace.append(f"{label}: recurring fee '{name}' {amount:g} x {months} months = {amount * months:g}")
        else:
            one_time += amount
            trace.append(f"{label}: one-time fee '{name}' = {amount:g}")

    discount = _num(quote.get("discount_amount", 0), f"{prefix}.discount_amount")
    if discount:
        trace.append(f"{label}: discount = -{discount:g}")

    total = recurring + one_time - discount
    if total < 0:
        raise InvalidInput(f"{prefix} total is negative ({total:g}); check discount and fees")
    trace.append(f"{label}: total over {months} months = {total:g}")

    unknowns: list[str] = []
    if not currency:
        unknowns.append("currency_not_specified")
    if period == "monthly" and quote.get("commitment_months") is None:
        unknowns.append("commitment_months_not_specified_assumed_12")
    if not fees:
        unknowns.append("no_itemized_fees_reported")
    if quote.get("tax_included") is None:
        unknowns.append("tax_treatment_not_specified")

    return {
        "supplier": label,
        "currency": currency or None,
        "billing_period": period,
        "term_months": months,
        "recurring_total": round(recurring, 2),
        "one_time_total": round(one_time, 2),
        "discount_total": round(discount, 2),
        "total_term": round(total, 2),
        "monthly_equivalent": round(total / months, 2),
        "unknowns": unknowns,
        "trace": trace,
    }


def normalize(quotes: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(quotes, list):
        raise InvalidInput("quotes must be a list")
    if not 2 <= len(quotes) <= 5:
        raise InvalidInput(f"quotes must contain 2 to 5 items, got {len(quotes)}")

    results = [normalize_quote(quote, index) for index, quote in enumerate(quotes)]

    warnings: list[str] = []
    currencies = {r["currency"] for r in results}
    if None in currencies:
        warnings.append("some_quotes_have_no_currency")
    elif len(currencies) > 1:
        warnings.append("currencies_differ_no_fx_conversion_performed")

    periods = {r["billing_period"] for r in results}
    if len(periods) > 1:
        warnings.append("billing_periods_differ_all_normalized_to_12_months")

    if any(r["one_time_total"] > 0 for r in results) and any(r["one_time_total"] == 0 for r in results):
        warnings.append("one_time_fees_present_in_some_quotes_only")

    ranked = sorted(results, key=lambda r: r["total_term"])

    by_currency: dict[str, list[dict[str, Any]]] = {}
    for item in results:
        key = item["currency"] or "UNSPECIFIED"
        by_currency.setdefault(key, []).append(item)
    ranking_by_currency = {
        key: [x["supplier"] for x in sorted(group, key=lambda y: y["total_term"])]
        for key, group in by_currency.items()
    }

    single_currency = len(by_currency) == 1 and "UNSPECIFIED" not in by_currency
    lowest_total = ranked[0]["supplier"] if single_currency else None

    return {
        "quote_count": len(results),
        "term_months": TERM_MONTHS,
        "lowest_total": lowest_total,
        "ranking_by_total_term": [r["supplier"] for r in ranked],
        "ranking_by_currency": ranking_by_currency,
        "quotes": results,
        "warnings": warnings,
        "notes": [
            "Amounts are computed only from the numbers supplied; missing amounts are never estimated.",
            "No currency conversion is performed; differing currencies are flagged, not converted.",
            "A single lowest total is reported only when all quotes share one specified currency.",
            "This output is arithmetic, not a purchase recommendation.",
        ],
    }


SAMPLE = [
    {
        "supplier": "Alpha",
        "currency": "USD",
        "billing_period": "monthly",
        "unit_price": 9.5,
        "quantity": 2,
        "commitment_months": 12,
        "fees": [{"label": "setup", "amount": 25}],
        "tax_included": False,
    },
    {
        "supplier": "Beta",
        "currency": "USD",
        "billing_period": "annual",
        "unit_price": 199,
        "quantity": 1,
        "fees": [],
    },
    {
        "supplier": "Gamma",
        "currency": "USD",
        "billing_period": "monthly",
        "unit_price": 8,
        "quantity": 2,
        "fees": [{"label": "support", "amount": 5, "recurring": True}],
    },
]


if __name__ == "__main__":
    import json

    out = normalize(SAMPLE)
    assert out["quote_count"] == 3
    alpha = out["quotes"][0]
    assert alpha["total_term"] == 253.0, alpha["total_term"]
    assert alpha["monthly_equivalent"] == 21.08, alpha["monthly_equivalent"]
    beta = out["quotes"][1]
    assert beta["total_term"] == 199.0, beta["total_term"]
    gamma = out["quotes"][2]
    assert gamma["total_term"] == 252.0, gamma["total_term"]
    assert "no_itemized_fees_reported" in beta["unknowns"]
    assert "commitment_months_not_specified_assumed_12" in gamma["unknowns"]
    assert "one_time_fees_present_in_some_quotes_only" in out["warnings"]
    assert out["lowest_total"] == "Beta"

    try:
        normalize([SAMPLE[0]])
    except InvalidInput as error:
        assert "2 to 5" in str(error)
    else:
        raise AssertionError("single quote should be rejected")

    try:
        normalize([{**SAMPLE[0], "unit_price": -1}, SAMPLE[1]])
    except InvalidInput as error:
        assert "negative" in str(error)
    else:
        raise AssertionError("negative price should be rejected")

    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("SELF-TEST PASSED")
