import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.market_data import market_manager
from engine.backtest_engine import run_strategy_backtest

def main():
    print("=== COIN STRATEJİ BACKTEST TESTİ ===")
    test_symbols = ["TRX/USDT", "BTC/USDT"]
    
    for sym in test_symbols:
        df = market_manager.get_market_data(sym, timeframe="1h", limit=500)
        if df is None:
            print(f"Hata: {sym} verisi alınamadı")
            continue
            
        res = run_strategy_backtest(sym, df, timeframe="1h", lookback=500)
        print(f"\n📌 {sym} (1h) - Toplam {res['lookback_candles']} Mum Test Edildi")
        champ = res.get('champion_strategy')
        if champ:
            print(f"🏆 1 NUMARALI ŞAMPİYON STRATEJİ: {champ['name']} ({champ['name_en']})")
            print(f"   Win Rate: %{champ['win_rate']} | Toplam İşlem: {champ['total_trades']} ({champ['wins']}W / {champ['losses']}L)")
            print(f"   Net Kâr: %{champ['net_profit_pct']} | Profit Factor: {champ['profit_factor']} | Max DD: %{champ['max_drawdown_pct']}")
        
        print("\n📊 LİDERLİK TABLOSU (İLK 5 STRATEJİ):")
        for i, s in enumerate(res['leaderboard'][:5], 1):
            print(f"   #{i} {s['name']:<35} | WR: %{s['win_rate']:<4} | İşlem: {s['total_trades']:<2} | Net: %{s['net_profit_pct']:<6} | PF: {s['profit_factor']}")

if __name__ == "__main__":
    main()
