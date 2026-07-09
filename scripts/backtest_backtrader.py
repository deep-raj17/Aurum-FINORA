"""Optional event-driven Backtrader validation with explicit costs and slippage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ohlcv", type=Path)
    parser.add_argument("--commission-bps", type=float, default=10)
    parser.add_argument("--slippage-bps", type=float, default=5)
    parser.add_argument("--output", type=Path, default=Path("reports/research/backtrader.json"))
    args = parser.parse_args()

    import backtrader as bt

    class MovingAverageCross(bt.Strategy):
        params = (("fast", 20), ("slow", 60))

        def __init__(self) -> None:
            self.signal = bt.ind.CrossOver(
                bt.ind.SMA(self.data.close, period=self.p.fast),
                bt.ind.SMA(self.data.close, period=self.p.slow),
            )

        def next(self) -> None:
            if self.signal > 0 and not self.position:
                self.buy()
            elif self.signal < 0 and self.position:
                self.close()

    frame = pd.read_csv(args.ohlcv, parse_dates=["timestamp"]).set_index("timestamp")
    required = {"open", "high", "low", "close", "volume"}
    if not required <= set(frame.columns):
        raise SystemExit(f"OHLCV file must include {sorted(required)}")
    engine = bt.Cerebro(stdstats=False)
    engine.adddata(bt.feeds.PandasData(dataname=frame))
    engine.addstrategy(MovingAverageCross)
    engine.broker.setcash(100_000)
    engine.broker.setcommission(commission=args.commission_bps / 10_000)
    engine.broker.set_slippage_perc(args.slippage_bps / 10_000)
    engine.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe")
    engine.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    starting = engine.broker.getvalue()
    strategy = engine.run()[0]
    ending = engine.broker.getvalue()
    payload = {
        "research_only": True,
        "strategy": "moving_average_cross",
        "starting_value": starting,
        "ending_value": ending,
        "net_return": ending / starting - 1,
        "commission_bps": args.commission_bps,
        "slippage_bps": args.slippage_bps,
        "sharpe": strategy.analyzers.sharpe.get_analysis(),
        "drawdown": strategy.analyzers.drawdown.get_analysis(),
        "alpha_claimed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
