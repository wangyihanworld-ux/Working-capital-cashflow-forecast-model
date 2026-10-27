"""Reproducible synthetic settlement comparison and optional local CSV inputs."""
import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import pandas as pd
from .settlement import SettlementTerms, compare_settlements, forecast_schedule


def demo_inputs():
    invoices = pd.DataFrame([
        ['SYN-001', '2027-01-20', 100.0], ['SYN-002', '2027-01-25', 40.0]],
        columns=['invoice_id', 'expected_date', 'amount_mn'])
    actuals = pd.DataFrame([['SYN-R001', 'SYN-001', '2027-01-08', 20.0, 19.9]],
                          columns=['receipt_id', 'invoice_id', 'actual_date', 'applied_mn', 'cash_mn'])
    outflows = pd.DataFrame([['2027-01-12', 80.0], ['2027-01-22', 50.0]], columns=['date', 'amount_mn'])
    terms = [SettlementTerms('bank_base', transfer_days=2),
             SettlementTerms('bank_earlier_collection', collection_shift_days=-12, transfer_days=2, fee_rate=.002),
             SettlementTerms('stablecoin_fast_transfer_only', conversion_days=1, redemption_days=1, fee_rate=.005, price_factor=.999),
             SettlementTerms('stablecoin_earlier_collection', collection_shift_days=-12, conversion_days=1,
                             redemption_days=1, fee_rate=.005, price_factor=.999),
             SettlementTerms('stablecoin_stress', collection_shift_days=-12, conversion_days=5,
                             redemption_days=3, fee_rate=.02, price_factor=.95,
                             redemption_open_date='2027-01-18', daily_capacity_mn=25),
             SettlementTerms('stablecoin_redemption_blocked', collection_shift_days=-12, redemption_allowed=False)]
    return invoices, actuals, outflows, terms


def generate_artifacts(folder):
    p = Path(folder); p.mkdir(parents=True, exist_ok=True)
    inv, act, pay, terms = demo_inputs()
    for name, frame in [('invoices', inv), ('actuals', act), ('outflows', pay)]:
        frame.to_csv(p/f'{name}.csv', index=False)
    (p/'terms.json').write_text(json.dumps([asdict(t) for t in terms], indent=2), encoding='utf-8')
    result = compare_settlements(inv, act, pay, terms, start='2027-01-01', end='2027-01-31',
                                 as_of='2027-01-08', opening_cash_mn=10, minimum_cash_mn=5)
    for name, frame in result.items():
        frame.to_csv(p/f'{name}.csv', index=False)
    # Also connect to the existing 12-month model without double counting.
    from .model import build_forecast
    from .synthetic import build_synthetic_dataset
    data = build_synthetic_dataset()
    f = build_forecast(data.history, data.assumptions.query("scenario == '基准'").iloc[0].to_dict())
    lots, payments = forecast_schedule(f)
    start = f.month.min(); end = f.month.max() + pd.offsets.MonthEnd(0)
    overlay_terms = [replace(t, redemption_open_date=(start+pd.Timedelta(days=17)).strftime('%Y-%m-%d'))
                     if t.redemption_open_date else t for t in terms]
    overlay = compare_settlements(lots, act.iloc[:0], payments,
                                  [SettlementTerms('monthly_baseline'), *overlay_terms], start=start, end=end,
                                  as_of=start-pd.Timedelta(days=1), opening_cash_mn=f.opening_cash_mn.iloc[0],
                                  minimum_cash_mn=float(data.assumptions.query("scenario == '基准'").minimum_cash_mn.iloc[0]))
    for name in ('summary', 'monthly', 'daily'):
        overlay[name].to_csv(p/f'model_overlay_{name}.csv', index=False)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', default='demo_output/settlement')
    parser.add_argument('--input-dir', help='Local CSV folder; never upload real payment records')
    parser.add_argument('--start'); parser.add_argument('--end'); parser.add_argument('--as-of')
    parser.add_argument('--opening-cash', type=float); parser.add_argument('--minimum-cash', type=float, default=0)
    args = parser.parse_args()
    if args.input_dir:
        if any(v is None for v in (args.start, args.end, args.as_of, args.opening_cash)):
            parser.error('Local inputs require --start, --end, --as-of and --opening-cash')
        p = Path(args.input_dir)
        terms = [SettlementTerms(**row) for row in json.loads((p/'terms.json').read_text(encoding='utf-8-sig'))]
        result = compare_settlements(pd.read_csv(p/'invoices.csv', dtype={'invoice_id': str}),
                                     pd.read_csv(p/'actuals.csv', dtype={'invoice_id': str, 'receipt_id': str}),
                                     pd.read_csv(p/'outflows.csv'), terms, start=args.start, end=args.end,
                                     as_of=args.as_of, opening_cash_mn=args.opening_cash, minimum_cash_mn=args.minimum_cash)
        out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
        for name, frame in result.items():
            frame.to_csv(out/f'{name}.csv', index=False)
    else:
        result = generate_artifacts(args.output_dir)
    print(result['summary'].to_string(index=False))


if __name__ == '__main__':
    main()
