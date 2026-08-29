import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.market_data import market_manager
from engine.patterns import detect_chart_patterns
from engine.pattern_radar import evaluate_coin_multi_timeframe_optimal, run_pattern_radar

def test_patterns_geometry():
    print("=== TESTING GEOMETRIC PATTERNS & AUTO TIMEFRAME DISCOVERY ===")
    
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "TRX/USDT", "DOGE/USDT"]
    for sym in symbols:
        print(f"\n--- Testing Auto Optimal Timeframe for {sym} ---")
        best = evaluate_coin_multi_timeframe_optimal(sym, target_timeframe="auto")
        if best:
            print(f"  ✅ Formasyon Bulundu: {best['strategy_name']}")
            print(f"  🌟 Seçilen İdeal Zaman Dilimi: {best['timeframe']} (Kalite: %{best['quality_score']})")
            print(f"  📍 Aşama: {best['stage_name']} | Yön: {best['direction']}")
            print(f"  🎯 Giriş: ${best['entry_price']} | SL: ${best['stop_loss']} | TP: ${best['take_profit']}")
            print(f"  📏 Çizgi Sayısı: {len(best.get('lines', []))}")
            if best.get('lines'):
                l0 = best['lines'][0]
                print(f"     -> Çizgi Adı: {l0['name']} ({len(l0.get('points', []))} enterpole nokta)")
                if l0.get('points'):
                    print(f"     -> Nokta 1: Time={l0['points'][0]['time']} Price={l0['points'][0]['value']}")
                    print(f"     -> Son Nokta: Time={l0['points'][-1]['time']} Price={l0['points'][-1]['value']}")
        else:
            print(f"  ⚪ {sym} için aktif formasyon bulunamadı.")

    print("\n--- Testing Full Multithreaded Pattern Radar (auto) ---")
    radar_res = run_pattern_radar(timeframe="auto", limit_coins=20)
    print("Radar Status:", radar_res["status"])
    print("Radar Stats:", radar_res["stats"])

if __name__ == "__main__":
    test_patterns_geometry()
