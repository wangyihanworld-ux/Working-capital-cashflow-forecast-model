import unittest
import pandas as pd
from working_capital.settlement import SettlementTerms as T, compare_settlements, forecast_schedule
from working_capital.settlement_demo import demo_inputs
from working_capital.validation import DataValidationError
from working_capital.synthetic import build_synthetic_dataset
from working_capital.model import build_forecast


class SettlementTest(unittest.TestCase):
    def setUp(self):
        self.inv, self.act, self.pay, self.terms = demo_inputs()

    def run_case(self, terms=None, **kwargs):
        opts = dict(start='2027-01-01', end='2027-01-31', as_of='2027-01-08', opening_cash_mn=10, minimum_cash_mn=5)
        opts.update(kwargs)
        return compare_settlements(self.inv, self.act, self.pay, terms or [T('base')], **opts)

    def test_partial_receipt_not_double_counted(self):
        r = self.run_case()
        self.assertAlmostEqual(r['daily'].actual_cash_mn.sum(), 19.9)
        self.assertAlmostEqual(r['daily'].forecast_cash_mn.sum(), 120)
        self.assertAlmostEqual(r['summary'].ending_cash_mn.iloc[0], 19.9)
        self.assertEqual(r['actual_audit'].days_vs_expected.iloc[0], -12)

    def test_actuals_are_fixed_across_scenarios(self):
        r = self.run_case(self.terms)
        values = r['daily'].groupby('scenario').actual_cash_mn.sum()
        self.assertTrue((values == 19.9).all())

    def test_cash_rollforward_and_monthly_reconciliation(self):
        r = self.run_case(self.terms); d = r['daily']
        residual = d.opening_cash_mn+d.actual_cash_mn+d.forecast_cash_mn-d.outflow_mn-d.ending_cash_mn
        self.assertLess(residual.abs().max(), 1e-9)
        for name, frame in d.groupby('scenario'):
            m = r['monthly'].query('scenario == @name')
            self.assertAlmostEqual(m.ending_cash_mn.iloc[-1], frame.ending_cash_mn.iloc[-1])

    def test_faster_transfer_alone_does_not_solve_payment_timing(self):
        s = self.run_case(self.terms)['summary'].set_index('scenario')
        self.assertAlmostEqual(s.loc['bank_base', 'maximum_gap_mn'], s.loc['stablecoin_fast_transfer_only', 'maximum_gap_mn'])
        self.assertGreater(s.loc['stablecoin_earlier_collection', 'peak_gap_reduction_vs_base_mn'], 0)
        self.assertLess(s.loc['stablecoin_earlier_collection', 'ending_cash_mn'], s.loc['bank_base', 'ending_cash_mn'])

    def test_price_and_fees_bridge(self):
        r = self.run_case([T('discount', price_factor=.9, fee_rate=.02, fixed_fee_mn=.1)])
        forecast = r['ledger'].query("source == 'forecast'")
        self.assertAlmostEqual(forecast.cash_mn.sum(), 120*.9*.98-.2)
        self.assertAlmostEqual((forecast.face_mn+forecast.price_effect_mn-forecast.fee_mn-forecast.cash_mn).sum(), 0)

    def test_blocked_redemption_never_becomes_cash(self):
        r = self.run_case([T('blocked', redemption_allowed=False)])
        self.assertEqual(r['daily'].forecast_cash_mn.sum(), 0)
        self.assertEqual(r['summary'].unsettled_face_mn.iloc[0], 120)

    def test_minimum_and_zero_capacity(self):
        for t in (T('minimum', minimum_redemption_mn=81), T('zero', daily_capacity_mn=0)):
            with self.subTest(t=t):
                self.assertEqual(self.run_case([t])['daily'].forecast_cash_mn.sum(), 0)

    def test_aggregate_capacity_and_face_conservation(self):
        self.inv.expected_date = '2027-01-20'
        r = self.run_case([T('capped', daily_capacity_mn=25)], end='2027-01-22')
        self.assertLessEqual(r['daily'].forecast_cash_mn.max(), 25)
        self.assertAlmostEqual(r['daily'].forecast_cash_mn.sum(), 75)
        self.assertAlmostEqual(r['summary'].unsettled_face_mn.iloc[0], 45)

    def test_redemption_window_and_delay(self):
        r = self.run_case([T('locked', redemption_open_date='2027-01-30', redemption_days=2)])
        self.assertEqual(r['daily'].forecast_cash_mn.sum(), 0)

    def test_past_actual_is_in_opening_not_counted_again(self):
        self.act.actual_date = '2026-12-31'
        r = self.run_case()
        self.assertEqual(r['daily'].actual_cash_mn.sum(), 0)
        self.assertEqual(r['daily'].forecast_cash_mn.sum(), 120)

    def test_overdue_remainder_not_injected_into_actual_period(self):
        self.inv.expected_date = '2026-12-01'
        d = self.run_case()['daily']
        self.assertEqual(d.loc[d.date <= pd.Timestamp('2027-01-08'), 'forecast_cash_mn'].sum(), 0)
        self.assertEqual(d.loc[d.date == pd.Timestamp('2027-01-09'), 'forecast_cash_mn'].iloc[0], 120)

    def test_invalid_actuals(self):
        for field, value in [('actual_date', '2027-01-09'), ('invoice_id', 'unknown'), ('applied_mn', 101), ('cash_mn', float('nan'))]:
            with self.subTest(field=field):
                self.setUp(); self.act.loc[0, field] = value
                with self.assertRaises(DataValidationError): self.run_case()

    def test_duplicate_receipts_rejected(self):
        self.act = pd.concat([self.act, self.act])
        with self.assertRaises(DataValidationError): self.run_case()

    def test_invalid_terms(self):
        for t in [T('bad', conversion_days=-1), T('bad', fee_rate=1.1), T('bad', price_factor=float('nan')), T('bad', fixed_fee_mn=1000)]:
            with self.subTest(t=t), self.assertRaises(DataValidationError): self.run_case([t])

    def test_daily_gap_hidden_by_month_end(self):
        s = self.run_case()['summary'].iloc[0]
        self.assertGreater(s.ending_cash_mn, 5)
        self.assertGreater(s.maximum_gap_mn, 50)
        self.assertGreater(s.gap_days, 0)

    def test_existing_forecast_adapter_matches_every_month(self):
        data = build_synthetic_dataset()
        f = build_forecast(data.history, data.assumptions.query("scenario == '基准'").iloc[0].to_dict())
        inv, pay = forecast_schedule(f)
        start = f.month.min()
        r = compare_settlements(inv, self.act.iloc[:0], pay, [T('base')], start=start,
                                end=f.month.max()+pd.offsets.MonthEnd(0), as_of=start-pd.Timedelta(days=1),
                                opening_cash_mn=f.opening_cash_mn.iloc[0])
        for actual, expected in zip(r['monthly'].ending_cash_mn, f.ending_cash_mn):
            self.assertAlmostEqual(actual, expected)

    def test_multiple_partial_payments_and_complete_settlement(self):
        self.act.loc[1] = ['SYN-R002', 'SYN-001', '2027-01-08', 80, 79.5]
        r = self.run_case()
        self.assertEqual(r['daily'].forecast_cash_mn.sum(), 40)
        self.assertAlmostEqual(r['daily'].actual_cash_mn.sum(), 99.4)

    def test_empty_receivables_leave_only_payments(self):
        self.inv = self.inv.iloc[:0]; self.act = self.act.iloc[:0]
        r = self.run_case()
        self.assertEqual(r['summary'].ending_cash_mn.iloc[0], -120)

    def test_no_forecast_cash_after_cutoff_at_horizon_end(self):
        r = self.run_case(as_of='2027-01-31')
        self.assertEqual(r['summary'].unsettled_face_mn.iloc[0], 120)

    def test_input_frames_are_not_mutated(self):
        snapshots = [x.copy(deep=True) for x in (self.inv, self.act, self.pay)]
        self.run_case(self.terms)
        for before, after in zip(snapshots, (self.inv, self.act, self.pay)):
            pd.testing.assert_frame_equal(before, after)


if __name__ == '__main__':
    unittest.main()
