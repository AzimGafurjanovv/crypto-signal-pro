import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.swing_radar import evaluate_swing_strategy_exact, run_swing_radar
from engine.market_data import market_manager

def test_swing_radar():
    print("=== TESTING SWING HIGH/LOW RADAR ENGINE ===")
    pairs = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT']
    for sym in pairs:
        df = market_manager.get_market_data(sym, timeframe="1h", limit=120)
        res = evaluate_swing_strategy_exact(sym, df, timeframe="1h", swing_lookback=3)
        json_out = {
            "status": res["status"],
            "direction": res["direction"],
            "invalid_reason": res["invalid_reason"],
            "swing_level": res["swing_level"],
            "swing_confirmed_time": res["swing_confirmed_time"],
            "breakout_time": res["breakout_time"],
            "breakout_level": res["breakout_level"],
            "retest_time": res["retest_time"],
            "confirmation_time": res["confirmation_time"],
            "entry_price": res["entry_price"],
            "stop_loss": res["stop_loss"],
            "take_profit": res["take_profit"],
            "risk_reward": res["risk_reward"]
        }
        print(f"\n--- {sym} ---")
        print(json.dumps(json_out, indent=2))

    print("\n=== RUNNING FULL SWING RADAR SCAN (30 COINS) ===")
    radar = run_swing_radar(timeframe="1h", limit_coins=30, swing_lookback=3)
    print("Swing Radar Stats:", radar["stats"])
    print("Stages Breakdown:")
    for stg, items in radar["stages"].items():
        print(f"  {stg.upper()} ({len(items)}): {[x['symbol'] + ' (' + x['direction'] + ')' for x in items]}")

if __name__ == "__main__":
    test_swing_radar()
