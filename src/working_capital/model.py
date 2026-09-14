import pandas as pd
from .validation import validate_history,validate_assumptions,DataValidationError

def build_forecast(history,assumption):
    h=validate_history(history); a=pd.DataFrame([assumption]) if isinstance(assumption,dict) else assumption
    a=validate_assumptions(a)
    if len(a)!=1: raise DataValidationError('单次预测必须且只能选择一个情景')
    p=a.iloc[0]; prior=h.iloc[-12:].copy(); months=pd.date_range(h.month.max()+pd.offsets.MonthBegin(1),periods=12,freq='MS')
    opening_ar=float(h.iloc[-1].ar_mn); opening_inv=float(h.iloc[-1].inventory_mn); opening_ap=float(h.iloc[-1].ap_mn); opening_cash=float(h.iloc[-1].cash_mn)
    rows=[]
    for i,month in enumerate(months):
        revenue=float(prior.iloc[i].revenue_mn)*(1+float(p.revenue_growth)); cogs=revenue*float(p.cogs_rate); opex=revenue*float(p.opex_rate)
        ar=revenue*12*float(p.dso)/365; inventory=cogs*12*float(p.dio)/365
        purchases=cogs+inventory-opening_inv; ap=purchases*12*float(p.dpo)/365
        collections=revenue+opening_ar-ar; supplier=purchases+opening_ap-ap
        ocf=collections-supplier-opex; cash=opening_cash+ocf; gap=max(float(p.minimum_cash_mn)-cash,0)
        dso=ar/(revenue*12)*365; dio=inventory/(cogs*12)*365; dpo=ap/(purchases*12)*365; ccc=dso+dio-dpo
        rows.append({'scenario':p.scenario,'month':month,'revenue_mn':revenue,'collections_mn':collections,'cogs_mn':cogs,'opening_inventory_mn':opening_inv,'purchases_mn':purchases,'ending_inventory_mn':inventory,'opening_ar_mn':opening_ar,'ending_ar_mn':ar,'opening_ap_mn':opening_ap,'ending_ap_mn':ap,'supplier_payments_mn':supplier,'opex_mn':opex,'operating_cashflow_mn':ocf,'opening_cash_mn':opening_cash,'ending_cash_mn':cash,'funding_gap_mn':gap,'dso':dso,'dio':dio,'dpo':dpo,'ccc':ccc})
        opening_ar,opening_inv,opening_ap,opening_cash=ar,inventory,ap,cash
    return pd.DataFrame(rows)

def summarize_scenarios(history,assumptions):
    a=validate_assumptions(assumptions); forecasts=pd.concat([build_forecast(history,row.to_dict()) for _,row in a.iterrows()],ignore_index=True)
    summary=forecasts.groupby('scenario',as_index=False).agg(revenue_mn=('revenue_mn','sum'),operating_cashflow_mn=('operating_cashflow_mn','sum'),minimum_cash_mn=('ending_cash_mn','min'),maximum_funding_gap_mn=('funding_gap_mn','max'),ending_cash_mn=('ending_cash_mn','last'),average_ccc=('ccc','mean'))
    order=pd.Categorical(summary.scenario,categories=['压力','基准','增长','改善'],ordered=True); summary=summary.assign(_o=order).sort_values('_o').drop(columns='_o').reset_index(drop=True)
    return {'forecast':forecasts,'summary':summary}

