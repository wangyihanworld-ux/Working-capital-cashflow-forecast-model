import unittest
import pandas as pd
from working_capital.comparison import cash_risk, compare
from working_capital.synthetic import build_synthetic_dataset


class ComparisonTests(unittest.TestCase):
    def test_monthly_gap_duration(self):
        risk = cash_risk(pd.DataFrame({'ending_cash_mn': [80, 70, 60, 90, 74]}), 75)
        self.assertEqual(risk['maximum_month_end_gap_mn'], 15)
        self.assertEqual(risk['gap_months'], 3)
        self.assertEqual(risk['longest_gap_months'], 2)

    def test_effects_reconcile_and_opex_hand_calculation(self):
        data = build_synthetic_dataset()
        assumptions = data.assumptions.set_index('scenario').to_dict('index')
        summary, bridge = compare(data.history, assumptions['基准'], assumptions['改善'])
        cash = summary.set_index('scenario').ending_cash_mn
        self.assertAlmostEqual(bridge.cash_change_mn.sum(), cash.combined-cash.base)
        expected = data.history.tail(12).revenue_mn.sum()*1.06*(.34-.325)
        self.assertAlmostEqual(bridge.set_index('effect').loc['opex', 'cash_change_mn'], expected)
        self.assertEqual(summary.set_index('scenario').loc['base', 'target_ccc'], 68)
        self.assertEqual(summary.set_index('scenario').loc['combined', 'target_ccc'], 40)
