# 营运资金与现金流预测模型

[![tests](https://github.com/wangyihanworld-ux/Working-capital-cashflow-forecast-model/actions/workflows/tests.yml/badge.svg)](https://github.com/wangyihanworld-ux/Working-capital-cashflow-forecast-model/actions/workflows/tests.yml)

这是作品集项目五，面向财务BP、FP&A和商业分析岗位。项目使用完全合成的数据，将销售、客户回款、库存采购、供应商付款和经营费用连接到月度现金余额，量化DSO、DIO、DPO和现金转换周期，并识别不同经营情景下的资金缺口。

> 所有企业、客户、供应商、金额和假设均为程序生成，不对应任何真实业务或银行账户。

## 业务问题

- 为什么收入增长时现金仍可能下降？
- 回款放慢、库存目标提高和供应商账期变化分别占用或释放多少现金？
- 压力、基准、增长和改善情景下，未来12个月最低现金余额是多少？
- 何时低于最低现金要求，资金缺口应如何披露？

## 核心模型

- 应收滚动：期初应收 + 收入 - 客户回款 = 期末应收
- 库存滚动：期初库存 + 采购 - 销售成本 = 期末库存
- 应付滚动：期初应付 + 采购 - 供应商付款 = 期末应付
- 现金滚动：期初现金 + 经营现金流 = 期末现金
- 经营现金流：客户回款 - 供应商付款 - 经营费用
- 现金转换周期：DSO + DIO - DPO

## 已实现

- 24个月可重复的合成历史数据和四类12个月预测情景；
- DSO、DIO、DPO驱动的应收、库存和应付滚动；
- 客户回款、采购、供应商付款、经营现金流和现金余额预测；
- 最低现金要求与逐月资金缺口预警；
- 一键输出合成输入文件和含12张工作表的管理报告；
- 20项自动化测试覆盖四套守恒关系、情景方向和输入边界。

## 一键运行

```powershell
python -m pip install -e .
python -m working_capital.demo
```

或运行：

```powershell
working-capital-demo --output-dir .\demo_output
```

## 运行测试

```powershell
python -m unittest discover -s tests -v
```

## 演示结果

压力情景经营现金流为-159.48百万元，最低现金为12.37百万元，最大资金缺口为62.63百万元；基准情景期末现金为245.41百万元；改善情景将平均现金转换周期从68天缩短至40天，期末现金提高到356.48百万元。

## 使用边界

- 情景是假设，不是概率或融资承诺；
- 天数法简化了月内回款和付款分布；
- 未纳入税费、资本开支、债务利息、股利和外汇现金流；
- 合成案例结果不能代表真实企业效果。

详细字段见[数据字典](docs/data-dictionary.md)，实施状态见[项目计划](docs/project-plan.md)。

