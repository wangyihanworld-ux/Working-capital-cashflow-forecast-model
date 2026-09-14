from dataclasses import dataclass
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class SyntheticDataset:
    history: pd.DataFrame
    assumptions: pd.DataFrame
    opening: dict

def build_synthetic_dataset(seed=51):
    rng=np.random.default_rng(seed); months=pd.date_range('2024-01-01',periods=24,freq='MS'); t=np.arange(24)
    revenue=105+1.15*t+12*np.sin(2*np.pi*t/12)+rng.normal(0,1.5,24)
    cogs=revenue*(0.61+rng.normal(0,0.006,24)); opex=revenue*(0.34+rng.normal(0,0.004,24))
    dso=46+3*np.sin(t/4); dio=58+4*np.cos(t/5); dpo=39+2*np.sin(t/6)
    ar=revenue*12*dso/365; inventory=cogs*12*dio/365
    purchases=np.empty(24); ap=np.empty(24); supplier=np.empty(24); collections=np.empty(24); cash=np.empty(24)
    prev_ar,prev_inv,prev_ap,prev_cash=150.0,130.0,92.0,85.0
    for i in range(24):
        purchases[i]=cogs[i]+inventory[i]-prev_inv; ap[i]=purchases[i]*12*dpo[i]/365
        collections[i]=revenue[i]+prev_ar-ar[i]; supplier[i]=purchases[i]+prev_ap-ap[i]
        cash[i]=prev_cash+collections[i]-supplier[i]-opex[i]
        prev_ar,prev_inv,prev_ap,prev_cash=ar[i],inventory[i],ap[i],cash[i]
    history=pd.DataFrame({'month':months,'revenue_mn':revenue,'cogs_mn':cogs,'opex_mn':opex,'ar_mn':ar,'inventory_mn':inventory,'ap_mn':ap,'collections_mn':collections,'purchases_mn':purchases,'supplier_payments_mn':supplier,'cash_mn':cash,'dso':dso,'dio':dio,'dpo':dpo})
    scenarios={'压力':(-0.08,64,82,32,0.64,0.38),'基准':(0.06,48,60,40,0.61,0.34),'增长':(0.18,55,70,38,0.615,0.35),'改善':(0.06,40,48,48,0.61,0.325)}
    rows=[]
    for name,v in scenarios.items():
        rows.append(dict(scenario=name,revenue_growth=v[0],dso=v[1],dio=v[2],dpo=v[3],cogs_rate=v[4],opex_rate=v[5],minimum_cash_mn=75.0))
    return SyntheticDataset(history,pd.DataFrame(rows),{'ar_mn':float(ar[-1]),'inventory_mn':float(inventory[-1]),'ap_mn':float(ap[-1]),'cash_mn':float(cash[-1])})
