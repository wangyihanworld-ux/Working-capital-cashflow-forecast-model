"""Daily available-cash scenarios, with an explicit observation cutoff.

All money is in millions of one reporting currency. Token balances are never
treated as spendable bank cash. Dates use calendar days, not banking calendars.
"""
from dataclasses import dataclass
import math
from numbers import Real
import pandas as pd
from .validation import DataValidationError


def _date(value):
    try:
        d = pd.Timestamp(value)
        if pd.isna(d) or d.tzinfo is not None or d != d.normalize():
            raise ValueError()
        return d
    except (ValueError, TypeError):
        raise DataValidationError('Dates must be valid timezone-free calendar dates') from None


def _number(value, name, minimum=0):
    try:
        v = float(value)
    except (ValueError, TypeError):
        raise DataValidationError(f'{name} must be numeric') from None
    if not math.isfinite(v) or (minimum is not None and v < minimum):
        raise DataValidationError(f'Invalid {name}')
    return v


@dataclass(frozen=True)
class SettlementTerms:
    name: str
    collection_shift_days: int = 0
    transfer_days: int = 0
    conversion_days: int = 0
    redemption_days: int = 0
    fee_rate: float = 0.0
    fixed_fee_mn: float = 0.0
    price_factor: float = 1.0
    redemption_allowed: bool = True
    redemption_open_date: str | None = None
    minimum_redemption_mn: float = 0.0
    daily_capacity_mn: float | None = None

    def validate(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise DataValidationError('Settlement name is required')
        for field in ('collection_shift_days', 'transfer_days', 'conversion_days', 'redemption_days'):
            v = getattr(self, field)
            if isinstance(v, bool) or not isinstance(v, int) or (field != 'collection_shift_days' and v < 0):
                raise DataValidationError(f'Invalid {field}')
        for field in ('fee_rate', 'fixed_fee_mn', 'price_factor', 'minimum_redemption_mn'):
            if not isinstance(getattr(self, field), Real) or isinstance(getattr(self, field), bool):
                raise DataValidationError(f'{field} must be a number')
            _number(getattr(self, field), field)
        if self.fee_rate > 1 or not isinstance(self.redemption_allowed, bool):
            raise DataValidationError('Invalid fee rate or redemption permission')
        if self.daily_capacity_mn is not None:
            if not isinstance(self.daily_capacity_mn, Real) or isinstance(self.daily_capacity_mn, bool):
                raise DataValidationError('Daily capacity must be a number')
            _number(self.daily_capacity_mn, 'daily capacity')
        if self.redemption_open_date is not None:
            _date(self.redemption_open_date)


def _table(frame, columns, dates=(), amounts=()):
    if not set(columns).issubset(frame.columns):
        raise DataValidationError('Required columns: ' + ', '.join(columns))
    out = frame.copy()
    for c in dates:
        out[c] = pd.to_datetime([_date(v) for v in out[c]])
    for c in amounts:
        out[c] = [_number(v, c) for v in out[c]]
    return out


def compare_settlements(invoices, actuals, outflows, terms, *, start, end, as_of,
                        opening_cash_mn, minimum_cash_mn=0):
    """Replace scheduled receipts with matched actuals; forecast only the balance.

    invoices: invoice_id, expected_date (payer release date), amount_mn.
    actuals: receipt_id, invoice_id, actual_date (bank cash available),
             applied_mn (face amount cleared), cash_mn (net cash received).
    outflows: date, amount_mn. Opening cash is immediately BEFORE start.
    Actuals before start reduce the invoice balance, but are already in opening
    cash. Actuals after as_of are rejected to avoid look-ahead bias. Unpaid
    overdue amounts are explicitly assumed payable no earlier than as_of+1.
    """
    start, end, as_of = map(_date, (start, end, as_of))
    if end < start or not start - pd.Timedelta(days=1) <= as_of <= end:
        raise DataValidationError('Require start-1 <= as_of <= end')
    opening = _number(opening_cash_mn, 'opening cash', None)
    threshold = _number(minimum_cash_mn, 'minimum cash')
    inv = _table(invoices, ['invoice_id', 'expected_date', 'amount_mn'], ['expected_date'], ['amount_mn'])
    act = _table(actuals, ['receipt_id', 'invoice_id', 'actual_date', 'applied_mn', 'cash_mn'],
                 ['actual_date'], ['applied_mn', 'cash_mn'])
    pay = _table(outflows, ['date', 'amount_mn'], ['date'], ['amount_mn'])
    for frame, col in ((inv, 'invoice_id'), (act, 'receipt_id')):
        if frame[col].isna().any() or frame[col].duplicated().any() or not frame[col].map(lambda x: isinstance(x, str) and bool(x.strip())).all():
            raise DataValidationError(f'{col} must contain unique nonempty strings')
    if not act.invoice_id.isin(inv.invoice_id).all() or (act.actual_date > as_of).any():
        raise DataValidationError('Unknown invoice or actual receipt after observation cutoff')
    if (act.applied_mn <= 0).any():
        raise DataValidationError('Actual applied amount must be positive')
    applied = act.groupby('invoice_id').applied_mn.sum()
    inv['remaining_mn'] = inv.amount_mn - inv.invoice_id.map(applied).fillna(0)
    if (inv.remaining_mn < -1e-9).any():
        raise DataValidationError('Actual allocations exceed invoice amount')
    inv['remaining_mn'] = inv.remaining_mn.clip(lower=0)
    if not terms or len({t.name for t in terms}) != len(terms):
        raise DataValidationError('Provide uniquely named settlement scenarios; first is baseline')
    if ((pay.date < start) | (pay.date > end)).any():
        raise DataValidationError('Outflow dates outside analysis horizon')
    audit = act.merge(inv[['invoice_id', 'expected_date']], on='invoice_id')
    audit['days_vs_expected'] = (audit.actual_date - audit.expected_date).dt.days
    audit['cash_difference_mn'] = audit.cash_mn - audit.applied_mn
    days = pd.date_range(start, end)
    daily_rows, ledgers, summaries = [], [], []
    for t in terms:
        t.validate()
        events = []
        for a in act.itertuples():
            events.append(dict(scenario=t.name, invoice_id=a.invoice_id, source='actual',
                               date=a.actual_date, face_mn=a.applied_mn, cash_mn=a.cash_mn,
                               fee_mn=0.0, price_effect_mn=0.0, status='actual_net_cash'))
        capacity_used = {}
        pending = []
        for row in inv.itertuples():
            amount = row.remaining_mn
            if amount <= 1e-9:
                continue
            # Timing adjustments affect only unsettled balances, never actuals.
            release = max(row.expected_date + pd.Timedelta(days=t.collection_shift_days),
                          as_of + pd.Timedelta(days=1))
            ready = release + pd.Timedelta(days=t.transfer_days + t.conversion_days)
            if t.redemption_open_date:
                ready = max(ready, _date(t.redemption_open_date))
            ready += pd.Timedelta(days=t.redemption_days)
            gross = amount * t.price_factor
            fee = gross * t.fee_rate + t.fixed_fee_mn
            _number(gross, 'converted proceeds'); _number(fee, 'total fee')
            if fee > gross:
                raise DataValidationError('Fees exceed proceeds; model explicit external fee outflows instead')
            reason = ('redemption_not_allowed' if not t.redemption_allowed else
                      'below_minimum_redemption' if amount < t.minimum_redemption_mn else
                      'zero_redemption_capacity' if t.daily_capacity_mn == 0 else None)
            pending.append((ready, row.invoice_id, amount, gross-fee, fee, gross-amount, reason))
        for ready, iid, amount, net, fee, price_effect, reason in sorted(pending):
            left = amount
            d = max(ready, start)
            while not reason and d <= end and left > 1e-9:
                capacity = left if t.daily_capacity_mn is None else max(t.daily_capacity_mn-capacity_used.get(d, 0), 0)
                take = min(left, capacity)
                if take > 1e-9:
                    fraction = take / amount
                    events.append(dict(scenario=t.name, invoice_id=iid, source='forecast', date=d,
                                       face_mn=take, cash_mn=net*fraction, fee_mn=fee*fraction,
                                       price_effect_mn=price_effect*fraction, status='available_cash'))
                    capacity_used[d] = capacity_used.get(d, 0) + take
                    left -= take
                d += pd.Timedelta(days=1)
            if left > 1e-9:
                fraction = left / amount
                events.append(dict(scenario=t.name, invoice_id=iid, source='forecast', date=pd.NaT,
                                   face_mn=left, cash_mn=net*fraction, fee_mn=fee*fraction,
                                   price_effect_mn=price_effect*fraction, status=reason or 'outside_horizon_or_capacity'))
        ledger = pd.DataFrame(events, columns=['scenario', 'invoice_id', 'source', 'date', 'face_mn', 'cash_mn', 'fee_mn', 'price_effect_mn', 'status'])
        ledger['date'] = pd.to_datetime(ledger.date)
        inside = ledger[ledger.date.between(start, end)]
        daily = pd.DataFrame({'date': days})
        for source, column in [('actual', 'actual_cash_mn'), ('forecast', 'forecast_cash_mn')]:
            receipts = inside[inside.source.eq(source)].groupby('date').cash_mn.sum()
            daily[column] = daily.date.map(receipts).fillna(0.0)
        daily['outflow_mn'] = daily.date.map(pay.groupby('date').amount_mn.sum()).fillna(0.0)
        daily['ending_cash_mn'] = opening + (daily.actual_cash_mn + daily.forecast_cash_mn - daily.outflow_mn).cumsum()
        daily['opening_cash_mn'] = daily.ending_cash_mn.shift(1, fill_value=opening)
        daily['funding_gap_mn'] = (threshold-daily.ending_cash_mn).clip(lower=0)
        daily['scenario'] = t.name
        longest = run = 0
        for gap in daily.funding_gap_mn:
            run = run+1 if gap > 1e-9 else 0
            longest = max(longest, run)
        summaries.append(dict(scenario=t.name, minimum_daily_cash_mn=daily.ending_cash_mn.min(),
                              maximum_gap_mn=daily.funding_gap_mn.max(), gap_days=int((daily.funding_gap_mn > 1e-9).sum()),
                              longest_gap_days=longest, gap_mn_days=daily.funding_gap_mn.sum(),
                              ending_cash_mn=daily.ending_cash_mn.iloc[-1],
                              realized_forecast_fees_mn=inside.fee_mn.sum(),
                              realized_price_effect_mn=inside.price_effect_mn.sum(),
                              unsettled_face_mn=ledger.loc[ledger.date.isna(), 'face_mn'].sum()))
        daily_rows.append(daily); ledgers.append(ledger)
    summary = pd.DataFrame(summaries)
    summary['peak_gap_reduction_vs_base_mn'] = summary.maximum_gap_mn.iloc[0] - summary.maximum_gap_mn
    summary['gap_days_reduction_vs_base'] = summary.gap_days.iloc[0] - summary.gap_days
    summary['ending_cash_change_vs_base_mn'] = summary.ending_cash_mn - summary.ending_cash_mn.iloc[0]
    daily = pd.concat(daily_rows, ignore_index=True)
    monthly = daily.assign(month=daily.date.dt.to_period('M').dt.to_timestamp()).groupby(['scenario', 'month'], as_index=False).agg(
        actual_cash_mn=('actual_cash_mn', 'sum'), forecast_cash_mn=('forecast_cash_mn', 'sum'),
        outflow_mn=('outflow_mn', 'sum'), ending_cash_mn=('ending_cash_mn', 'last'),
        maximum_daily_gap_mn=('funding_gap_mn', 'max'))
    return dict(summary=summary, daily=daily, monthly=monthly,
                ledger=pd.concat(ledgers, ignore_index=True), actual_audit=audit)


def forecast_schedule(forecast):
    """Explicit month-end timing assumption for one existing forecast scenario.

    These synthetic receipt lots represent forecast collections, NOT invoices
    or a new AR ledger. Replace this adapter with real dated input for analysis.
    Collections are replaced, never added a second time to model cash flow.
    """
    if forecast.empty or forecast.scenario.nunique() != 1 or forecast.month.duplicated().any():
        raise DataValidationError('Select one nonempty monthly forecast scenario')
    f = forecast.sort_values('month')
    dates = pd.to_datetime(f.month) + pd.offsets.MonthEnd(0)
    invoices = pd.DataFrame({'invoice_id': [f'LOT-{i+1:03}' for i in range(len(f))],
                             'expected_date': dates.to_numpy(), 'amount_mn': f.collections_mn.to_numpy()})
    outflows = pd.DataFrame({'date': dates.to_numpy(), 'amount_mn': (f.supplier_payments_mn+f.opex_mn).to_numpy()})
    return invoices, outflows
