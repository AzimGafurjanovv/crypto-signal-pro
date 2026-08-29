import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.pattern_radar import run_pattern_radar

def test_pattern_radar():
    print("=== TESTING CHART PATTERN RADAR ENGINE ===")
    res = run_pattern_radar(timeframe="1h", limit_coins=20)
    print("Pattern Radar Status:", res.get("status"))
    print("Stats:", res.get("stats"))
    print("Breakout count:", len(res['stages']['breakout']))
    print("Retest count:", len(res['stages']['retesting']))
    print("Confirmed count:", len(res['stages']['confirmed']))
    
    if res['stages']['confirmed']:
        sample = res['stages']['confirmed'][0]
        print(f"\nSample Confirmed Pattern: {sample['symbol']} -> {sample['strategy_name']} ({sample['direction']})")
        print(f"  Entry: ${sample['entry_price']} | SL: ${sample['stop_loss']} | TP: ${sample['take_profit']}")
    elif res['stages']['retesting']:
        sample = res['stages']['retesting'][0]
        print(f"\nSample Retesting Pattern: {sample['symbol']} -> {sample['strategy_name']} ({sample['direction']})")
    elif res['stages']['breakout']:
        sample = res['stages']['breakout'][0]
        print(f"\nSample Breakout Pattern: {sample['symbol']} -> {sample['strategy_name']} ({sample['direction']})")

if __name__ == "__main__":
    test_pattern_radar()
