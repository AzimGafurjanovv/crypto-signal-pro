import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.pdh_pdl_radar import run_pdh_pdl_radar
from engine.swing_radar import run_swing_radar

def test_both_radars():
    print("=== 1. TESTING PDH / PDL RADAR ===")
    pdh_res = run_pdh_pdl_radar(timeframe="1h", limit_coins=20)
    print("PDH/PDL Stats:", pdh_res['stats'])
    
    print("\n=== 2. TESTING SWING HIGH/LOW RADAR ===")
    swing_res = run_swing_radar(timeframe="1h", limit_coins=20, swing_lookback=3)
    print("Swing Stats:", swing_res['stats'])
    print("Swing Retesting count:", len(swing_res['stages']['retesting']))
    print("Swing Breakout count:", len(swing_res['stages']['breakout']))
    print("Swing Confirmed count:", len(swing_res['stages']['confirmed']))

if __name__ == "__main__":
    test_both_radars()
