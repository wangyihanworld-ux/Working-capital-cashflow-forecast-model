import argparse
from .synthetic import build_synthetic_dataset
from .model import summarize_scenarios
from .reporting import generate_demo_artifacts
from .settlement_demo import generate_artifacts as generate_settlement_artifacts
from pathlib import Path
def main():
    p=argparse.ArgumentParser(); p.add_argument('--output-dir',default='demo_output'); a=p.parse_args(); d=build_synthetic_dataset(); r=summarize_scenarios(d.history,d.assumptions); i,o=generate_demo_artifacts(a.output_dir)
    print('营运资金与现金流预测Demo（全部为合成数据）'); print(r['summary'].to_string(index=False)); print(f'合成输入：{i.resolve()}'); print(f'管理报告：{o.resolve()}')
    settlement = generate_settlement_artifacts(Path(a.output_dir)/'settlement')
    print('逐笔结算与每日资金缺口（合成情景，金额百万元）')
    print(settlement['summary'].to_string(index=False))
if __name__=='__main__': main()

