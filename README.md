# quote-normalizer

Compare supplier quotes on the same basis: one 12-month total per quote, a step-by-step arithmetic trace, and an explicit list of what the quote did **not** state.

Built for the case where two quotes are not comparable at a glance — one is monthly, one is annual, one has a setup fee, one has a monthly support line, and nobody wrote down the commitment period.

## What it does

- Normalizes monthly, annual and one-time pricing to a common 12-month total
- Separates recurring cost, one-time fees, and discounts
- Returns a monthly equivalent per quote
- Lists structural unknowns (missing currency, missing commitment period, no itemized fees, tax not stated)
- Flags non-comparable inputs (different currencies, mixed billing periods, one-time fees in only some quotes)

## What it does not do

- **No extraction.** It does not read PDFs, images, emails or web pages. Input must already be structured JSON.
- **No currency conversion.** Different currencies are grouped and ranked separately, never converted.
- **No guessing.** A missing amount stays missing and is reported as an unknown.
- **No recommendation.** Output is arithmetic, not advice on which supplier to choose.

## Usage

```bash
python3 cli.py examples/sample_input.json
```

```
Supplier      Currency         Total   Per month
------------------------------------------------
Alpha         USD             253.00       21.08
Beta          USD             199.00       16.58
Gamma         USD             252.00       16.58
```

Options:

```bash
python3 cli.py quotes.json --trace   # show every arithmetic step
python3 cli.py quotes.json --json    # machine-readable result
```

## Input format

```json
{
  "quotes": [
    {
      "supplier": "Alpha",
      "currency": "USD",
      "billing_period": "monthly",
      "unit_price": 9.5,
      "quantity": 2,
      "commitment_months": 12,
      "discount_amount": 0,
      "tax_included": false,
      "fees": [{ "label": "setup", "amount": 25 }]
    }
  ]
}
```

`billing_period` must be `monthly`, `annual` or `one_time`. Between 2 and 5 quotes per run.

A fee with `"recurring": true` is charged every month; anything else is treated as one-time.

## Library use

```python
from quote_norm import normalize, InvalidInput

result = normalize(quotes)          # raises InvalidInput on bad data
print(result["lowest_total"])       # None when currencies differ
```

## Behavior on bad input

Invalid input raises `InvalidInput` with the exact field, and the CLI exits with code 2:

```
$ python3 cli.py bad.json
Invalid input: quotes[1].unit_price must not be negative, got -5
```

Rejected cases: fewer than 2 or more than 5 quotes, unknown billing period, negative amounts, negative total.

## Design notes

- Pure functions, no network, no I/O in the core module.
- When quotes use different currencies, no single "lowest" is declared; results are ranked per currency instead.
- Absent values are never filled in with plausible defaults. A monthly quote without a commitment period is computed on 12 months **and** flagged.

## Related

Notes on choosing and running small servers, written from an actual rental: <https://agentshopping.org/>
