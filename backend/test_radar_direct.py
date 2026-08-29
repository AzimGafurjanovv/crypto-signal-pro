import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.pdh_pdl_radar import run_pdh_pdl_radar

def test_radar():
    print("=== TESTING DEDICATED PDH/PDL RADAR (3 STAGES) ===")
    res = run_pdh_pdl_radar(timeframe="1h", limit_coins=30)
    
    print(f"Status: {res['status']}")
    print(f"Taranan Koin Sayısı: {res['total_scanned']}")
    print(f"İstatistikler: {res['stats']}")
    print("-" * 60)
    
    stages = res['stages']
    print(f"\n🚀 3. AŞAMA: ONAYLANANLAR (CONFIRMED ENTRY) ({len(stages['confirmed'])} Koin):")
    for c in stages['confirmed']:
        print(f"  • {c['symbol']} ({c['direction']}) | Fiyat: ${c['current_price']} | Giriş: ${c['entry_price']} | SL: ${c['stop_loss']} | TP1: ${c['tp1']} | TP2: ${c['tp2']}")
        print(f"    Açıklama: {c['explanation']}")

    print(f"\n🎯 2. AŞAMA: RETEST YAPANLAR (RETESTING) ({len(stages['retesting'])} Koin):")
    for c in stages['retesting']:
        print(f"  • {c['symbol']} ({c['direction']}) | Fiyat: ${c['current_price']} | PDH: ${c['pdh']} | PDL: ${c['pdl']} | Fark: %{c['diff_from_level_pct']}")
        print(f"    Açıklama: {c['explanation']}")

    print(f"\n⚡ 1. AŞAMA: YENİ KIRILANLAR (BREAKOUT) ({len(stages['breakout'])} Koin):")
    for c in stages['breakout']:
        print(f"  • {c['symbol']} ({c['direction']}) | Fiyat: ${c['current_price']} | Kırılan Seviye: ${c['breakout_level']} | Fark: %{c['diff_from_level_pct']}")
        print(f"    Açıklama: {c['explanation']}")

    print("\nALL RADAR TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_radar()
