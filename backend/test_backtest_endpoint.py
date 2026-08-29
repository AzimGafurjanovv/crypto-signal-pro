import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import get_strategy_backtest

async def test():
    print("=== TESTING BACKTEST ENDPOINT ===")
    
    # 1. Test AVAX/USDT backtest
    print("Running backtest for AVAX/USDT (1h, 500 candles)...")
    res_avax = await get_strategy_backtest(symbol="AVAX/USDT", timeframe="1h", limit=500)
    print("[✓] AVAX Backtest status:", res_avax.get("status"))
    print("[✓] Best Strategy:", res_avax.get("best_strategy", {}).get("name"))
    print("[✓] Total Strategies Tested:", len(res_avax.get("all_strategies", [])))
    assert res_avax.get("status") == "success"
    
    # 2. Test BTC/USDT backtest
    print("\nRunning backtest for BTC/USDT (1h, 500 candles)...")
    res_btc = await get_strategy_backtest(symbol="BTC/USDT", timeframe="1h", limit=500)
    print("[✓] BTC Backtest status:", res_btc.get("status"))
    print("[✓] Best Strategy:", res_btc.get("best_strategy", {}).get("name"))
    print("[✓] Best Strategy Win Rate: %", res_btc.get("best_strategy", {}).get("win_rate"))
    print("[✓] Best Strategy Profit: %", res_btc.get("best_strategy", {}).get("net_profit_pct"))
    assert res_btc.get("status") == "success"
    
    print("\nALL BACKTEST TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test())
