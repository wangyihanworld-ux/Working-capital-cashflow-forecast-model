# Working Capital and Cash-flow Forecast

[中文](README.md) · English

Connect sales growth and working-capital terms to cash balances and explicitly visible funding gaps.

## Analytical approach and deliverables

- Roll forward receivables, inventory, payables and cash monthly, using DSO/DIO/DPO targets.
- Require at least 12 continuous historical months and finite inputs; normalize dates before detecting duplicate months.
- Consume excess inventory over time instead of creating negative purchases. Show inventory targets and excess inventory separately.
- Cap receivables/payables by available balances to avoid negative collections/payments; achieved days may differ from targets.
- Keep cash calculations valid when revenue, cost or purchases are zero. Undefined turnover ratios and CCC appear blank, not zero.

The synthetic stress scenario has a CNY 62.63 million maximum funding gap. No automatic borrowing conceals that gap.

## Reproduce

Run from the repository root with Python 3.12:

```powershell
python -m pip install -e .
python -m working_capital.demo
python -m unittest discover -s tests -v
```

## Interpretation and limitations

Monthly annualization uses a 365-day convention. Excess inventory is not assumed to be returned, written off or converted to cash. Mean CCC excludes undefined months. Tax, capex, debt service, dividends and FX cash flows are outside scope. This is not a daily liquidity schedule.

Business examples use synthetic data and contain no private company or customer records. Only the separately labelled World Bank case in the macro repository uses public economic observations. Refer to current source and CI for this update; older release tags and screenshots describe earlier snapshots.
