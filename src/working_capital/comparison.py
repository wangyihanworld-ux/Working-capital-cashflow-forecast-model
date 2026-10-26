"""Controlled synthetic cash comparisons; month-end balances, not intramonth peaks."""
from pathlib import Path
import pandas as pd
from .model import build_forecast
from .synthetic import build_synthetic_dataset


def cash_risk(forecast, minimum_cash):
    gaps = (minimum_cash - forecast.ending_cash_mn).clip(lower=0)
    longest = current = 0
    for gap in gaps:
        current = current + 1 if gap > 0 else 0
        longest = max(longest, current)
    return dict(minimum_month_end_cash_mn=float(forecast.ending_cash_mn.min()),
                maximum_month_end_gap_mn=float(gaps.max()),
                gap_months=int((gaps > 0).sum()), longest_gap_months=longest,
                ending_cash_mn=float(forecast.ending_cash_mn.iloc[-1]))


def compare(history, base, improved):
    """Hold revenue and COGS fixed; separate turnover and OPEX effects.

    The interaction is reported, never silently allocated. Stress assumptions
    combine delayed collections and slower inventory, not independent probabilities.
    """
    turnover = {key: improved[key] for key in ('dso', 'dio', 'dpo')}
    cases = {'base': {}, 'turnover_only': turnover,
             'opex_only': {'opex_rate': improved['opex_rate']},
             'combined': {**turnover, 'opex_rate': improved['opex_rate']},
             'collection_inventory_stress': {'dso': base['dso'] + 10, 'dio': base['dio'] + 15}}
    rows = []
    for name, changes in cases.items():
        assumptions = {**base, **changes, 'scenario': name}
        forecast = build_forecast(history, assumptions)
        rows.append(dict(scenario=name, target_ccc=assumptions['dso']+assumptions['dio']-assumptions['dpo'],
                         minimum_cash_assumption_mn=assumptions['minimum_cash_mn'],
                         **cash_risk(forecast, assumptions['minimum_cash_mn'])))
    result = pd.DataFrame(rows)
    cash = result.set_index('scenario').ending_cash_mn
    effects = pd.DataFrame([
        {'effect': 'turnover', 'cash_change_mn': cash.turnover_only-cash.base},
        {'effect': 'opex', 'cash_change_mn': cash.opex_only-cash.base},
        {'effect': 'interaction', 'cash_change_mn': cash.combined-cash.turnover_only-cash.opex_only+cash.base},
    ])
    return result, effects


def main():
    data = build_synthetic_dataset()
    assumptions = data.assumptions.set_index('scenario').to_dict('index')
    summary, bridge = compare(data.history, assumptions['基准'], assumptions['改善'])
    out = Path('docs/evidence'); out.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out/'controlled_cash_comparison.csv', index=False)
    bridge.to_csv(out/'cash_change_attribution.csv', index=False)
    print(summary.to_string(index=False)); print(bridge.to_string(index=False))


if __name__ == '__main__':
    main()
