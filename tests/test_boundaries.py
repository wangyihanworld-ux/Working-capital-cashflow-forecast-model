import unittest
import numpy as np
import pandas as pd
from working_capital.synthetic import build_synthetic_dataset
from working_capital.model import build_forecast
from working_capital.validation import DataValidationError


class BoundaryTest(unittest.TestCase):
    def setUp(self):
        self.data = build_synthetic_dataset()
        self.base = self.data.assumptions.iloc[1].to_dict()

    def test_zero_cost_and_zero_sales_keep_cash_finite(self):
        for changes in ({'cogs_rate': 0}, {'revenue_growth': -1}):
            f = build_forecast(self.data.history, {**self.base, **changes})
            self.assertTrue(np.isfinite(f.ending_cash_mn).all())
            self.assertTrue(f.dio.isna().all())
            self.assertTrue(f.ccc.isna().all())

    def test_inventory_is_consumed_instead_of_negative_purchases(self):
        f = build_forecast(self.data.history, {**self.base, 'dio': 0})
        self.assertEqual(f.purchases_mn.iloc[0], 0)
        self.assertGreater(f.ending_inventory_mn.iloc[0], 0)
        self.assertTrue((f[['purchases_mn', 'ending_ap_mn', 'supplier_payments_mn']] >= 0).all().all())
        np.testing.assert_allclose(f.opening_inventory_mn + f.purchases_mn - f.cogs_mn, f.ending_inventory_mn)
        np.testing.assert_allclose(f.opening_ap_mn + f.purchases_mn - f.supplier_payments_mn, f.ending_ap_mn)

    def test_extreme_terms_do_not_create_negative_cash_receipts(self):
        f = build_forecast(self.data.history, {**self.base, 'dso': 1000, 'dpo': 1000})
        self.assertTrue((f[['collections_mn', 'supplier_payments_mn']] >= 0).all().all())
        np.testing.assert_allclose(f.opening_ar_mn + f.revenue_mn - f.collections_mn, f.ending_ar_mn)

    def test_short_gapped_and_duplicate_calendar_months_rejected(self):
        duplicate = self.data.history.copy()
        duplicate.loc[1, 'month'] = duplicate.loc[0, 'month'] + pd.Timedelta(days=5)
        for h in (self.data.history.tail(6), self.data.history.drop(index=5), duplicate):
            with self.assertRaises(DataValidationError):
                build_forecast(h, self.base)

    def test_nonfinite_and_below_minus100_growth_rejected(self):
        for changes in ({'dso': np.inf}, {'revenue_growth': -1.01}, {'scenario': ' '}):
            with self.assertRaises(DataValidationError):
                build_forecast(self.data.history, {**self.base, **changes})

    def test_negative_opening_cash_is_allowed(self):
        h = self.data.history.copy()
        h.loc[h.index[-1], 'cash_mn'] = -5
        self.assertEqual(build_forecast(h, self.base).opening_cash_mn.iloc[0], -5)
