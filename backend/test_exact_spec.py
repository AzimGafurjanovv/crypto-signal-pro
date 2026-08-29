import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.pdh_pdl_radar import evaluate_pdh_pdl_exact, run_pdh_pdl_radar
from engine.market_data import market_manager

def test_exact_specification():
    print("=== TESTING EXACT PDH/PDL SPECIFICATION ===")
    pairs = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'DOGE/USDT', 'ADA/USDT', 'LINK/USDT']
    
    for sym in pairs:
        df = market_manager.get_market_data(sym, timeframe="1h", limit=120)
        res = evaluate_pdh_pdl_exact(sym, df, timeframe="1h")
        
        # Test JSON serialization
        json_output = {
            "status": res["status"],
            "direction": res["direction"],
            "invalid_reason": res["invalid_reason"],
            "prev_day_high": res["prev_day_high"],
            "prev_day_low": res["prev_day_low"],
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
        print(json.dumps(json_output, indent=2))
        if res['checklist']:
            print("Checklist:")
            for chk in res['checklist']:
                print(f"  {'✅' if chk['passed'] else '❌'} {chk['title']}: {chk['detail']}")

    print("\n=== RUNNING FULL RADAR SCAN ===")
    radar_res = run_pdh_pdl_radar(timeframe="1h", limit_coins=30)
    print("Radar Stats:", radar_res['stats'])

if __name__ == "__main__":
    test_exact_specification()
