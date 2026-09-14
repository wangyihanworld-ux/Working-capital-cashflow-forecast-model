# 数据字典与业务口径

金额单位均为百万元，日期为月初。

| 字段 | 含义 |
|---|---|
| revenue_mn | 当月收入 |
| collections_mn | 当月客户回款 |
| cogs_mn | 当月销售成本 |
| purchases_mn | 当月采购 |
| supplier_payments_mn | 当月供应商付款 |
| ar_mn / ending_ar_mn | 期末应收账款 |
| inventory_mn / ending_inventory_mn | 期末库存 |
| ap_mn / ending_ap_mn | 期末应付账款 |
| operating_cashflow_mn | 客户回款减供应商付款和经营费用 |
| ending_cash_mn | 未假设自动融资的期末现金 |
| funding_gap_mn | 最低现金要求减期末现金，最低为零 |
| DSO | 应收账款周转天数 |
| DIO | 库存周转天数 |
| DPO | 应付账款周转天数 |
| CCC | DSO + DIO - DPO |

增长情景用于说明快速增长也可能消耗现金；改善情景同时缩短DSO和DIO、合理延长DPO。模型不会自动注入融资，因此资金缺口保持可见。

