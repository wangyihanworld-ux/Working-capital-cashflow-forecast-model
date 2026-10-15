import pandas as pd
import numpy as np
class DataValidationError(ValueError): pass
HISTORY_COLS=['month','revenue_mn','cogs_mn','opex_mn','ar_mn','inventory_mn','ap_mn','cash_mn']
ASSUMPTION_COLS=['scenario','revenue_growth','dso','dio','dpo','cogs_rate','opex_rate','minimum_cash_mn']
def validate_history(frame):
    miss=[c for c in HISTORY_COLS if c not in frame.columns]
    if miss: raise DataValidationError(f'缺少历史字段: {miss}')
    if frame.empty: raise DataValidationError('历史数据不能为空')
    x=frame.copy(); x['month']=pd.to_datetime(x['month'],errors='coerce').dt.to_period('M').dt.to_timestamp()
    for c in HISTORY_COLS[1:]: x[c]=pd.to_numeric(x[c],errors='coerce')
    if x[HISTORY_COLS].isna().any().any(): raise DataValidationError('历史数据存在空值或无效值')
    if x.month.duplicated().any(): raise DataValidationError('历史月份不能重复')
    if not np.isfinite(x[HISTORY_COLS[1:]].to_numpy(float)).all(): raise DataValidationError('历史金额必须为有限数字')
    if len(x)<12: raise DataValidationError('历史数据至少需要12个连续月份')
    ordered=x.month.sort_values()
    if not pd.DatetimeIndex(ordered).equals(pd.date_range(ordered.min(),ordered.max(),freq='MS')): raise DataValidationError('历史月份必须连续')
    if (x[[c for c in HISTORY_COLS[1:] if c != 'cash_mn']]<0).any().any(): raise DataValidationError('历史金额不能为负数')
    return x.sort_values('month').reset_index(drop=True)
def validate_assumptions(frame):
    miss=[c for c in ASSUMPTION_COLS if c not in frame.columns]
    if miss: raise DataValidationError(f'缺少情景字段: {miss}')
    x=frame.copy()
    if x.empty: raise DataValidationError('情景不能为空')
    x['scenario']=x['scenario'].astype('string').str.strip()
    if x.scenario.isna().any() or x.scenario.eq('').any(): raise DataValidationError('情景名称不能为空')
    for c in ASSUMPTION_COLS[1:]: x[c]=pd.to_numeric(x[c],errors='coerce')
    if x[ASSUMPTION_COLS].isna().any().any(): raise DataValidationError('情景存在空值或无效值')
    if not np.isfinite(x[ASSUMPTION_COLS[1:]].to_numpy(float)).all(): raise DataValidationError('情景参数必须为有限数字')
    if (x.revenue_growth < -1).any(): raise DataValidationError('收入增长率不能低于-100%')
    if x.scenario.duplicated().any(): raise DataValidationError('情景名称不能重复')
    if (x[['dso','dio','dpo','minimum_cash_mn']]<0).any().any(): raise DataValidationError('天数和最低现金不能为负数')
    if ((x[['cogs_rate','opex_rate']]<0)|(x[['cogs_rate','opex_rate']]>1)).any().any(): raise DataValidationError('成本率必须在0到1之间')
    return x

