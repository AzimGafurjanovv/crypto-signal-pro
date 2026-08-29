import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.market_data import market_manager
from engine.backtest_engine import run_strategy_backtest

def test_formasyon_backtest():
    print("=== TESTING FORMASYON & STRATEGY BACKTEST ===")
    df = market_manager.get_market_data("BTC/USDT", timeframe="1h", limit=500)
    print("Fetched df candles:", len(df))
    
    res = run_strategy_backtest("BTC/USDT", df, timeframe="1h", lookback=500)
    print("Backtest status:", res.get("status"))
    print("Champion strategy:", res.get("champion_strategy", {}).get("name"))
    print("Total strategies tested:", len(res.get("leaderboard", [])))
    
    for s in res.get("leaderboard", []):
        print(f"  -> [{s['id']}] {s['name']}: {s['total_trades']} Trades | Win Rate: %{s['win_rate']} | Net PnL: %{s['net_profit_pct']}")

if __name__ == "__main__":
    test_formasyon_backtest()
