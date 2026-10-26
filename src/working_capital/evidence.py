"""Cash/profit reconciliation and controlled sensitivities; synthetic demonstration."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from .model import build_forecast
from .synthetic import build_synthetic_dataset

def profit_cash_bridge(forecast):
    f=forecast
    out=f[['scenario','month']].copy()
    out['operating_profit_mn']=f.revenue_mn-f.cogs_mn-f.opex_mn
    out['ar_cash_effect_mn']=f.opening_ar_mn-f.ending_ar_mn
    out['inventory_cash_effect_mn']=f.opening_inventory_mn-f.ending_inventory_mn
    out['ap_cash_effect_mn']=f.ending_ap_mn-f.opening_ap_mn
    out['indirect_ocf_mn']=out[['operating_profit_mn','ar_cash_effect_mn','inventory_cash_effect_mn','ap_cash_effect_mn']].sum(axis=1)
    out['direct_ocf_mn']=f.operating_cashflow_mn
    out['reconciliation_difference_mn']=out.indirect_ocf_mn-out.direct_ocf_mn
    return out

def one_factor_sensitivity(history, assumption, delta_days=10):
    if not np.isfinite(delta_days) or delta_days <= 0:
        raise ValueError('delta_days must be positive and finite')
    base=build_forecast(history,assumption)
    rows=[]
    for driver in ['dso','dio','dpo']:
        for change in [-delta_days,delta_days]:
            value=float(assumption[driver])+change
            if value<0: continue
            p=dict(assumption); p[driver]=value
            f=build_forecast(history,p)
            rows.append({'driver':driver,'base_days':assumption[driver], 'scenario_days':value,
                         'delta_days':change,'ending_cash_mn':f.ending_cash_mn.iloc[-1],
                         'change_vs_base_mn':f.ending_cash_mn.iloc[-1]-base.ending_cash_mn.iloc[-1],
                         'maximum_gap_mn':f.funding_gap_mn.max(),
                         'zero_purchase_months':int(f.purchases_mn.eq(0).sum()),
                         'above_target_inventory_months':int(f.inventory_above_target_mn.gt(0).sum())})
    return pd.DataFrame(rows)

def main():
    p=argparse.ArgumentParser(); p.add_argument('--output-dir',default='docs/evidence'); a=p.parse_args()
    out=Path(a.output_dir); out.mkdir(parents=True,exist_ok=True)
    d=build_synthetic_dataset(); base=d.assumptions.query("scenario=='基准'").iloc[0].to_dict()
    f=build_forecast(d.history,base)
    bridge=profit_cash_bridge(f); sensitivity=one_factor_sensitivity(d.history,base)
    if bridge.reconciliation_difference_mn.abs().max()>1e-8: raise ValueError('Cash bridge failed')
    bridge.to_csv(out/'profit_cash_bridge.csv',index=False)
    sensitivity.to_csv(out/'one_factor_sensitivity.csv',index=False)
    print('Synthetic scenario evidence; amounts in millions; no corporate impact claim.')
    print(sensitivity.to_string(index=False))

if __name__=='__main__': main()
