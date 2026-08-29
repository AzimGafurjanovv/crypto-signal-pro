import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.market_data import market_manager
from engine.setup_calculator import calculate_crypto_setup

async def test_live_pdh_filter():
    print("=== TESTING LIVE PDH/PDL (BENİM) STRATEGY FILTER ON 25 TOP COINS ===")
    pairs = market_manager.get_top_pairs(limit=25)
    matched_coins = []

    for sym in pairs:
        df = market_manager.get_market_data(sym, timeframe="1h", limit=100)
        if df is not None and len(df) >= 40:
            setup = calculate_crypto_setup(sym, df, timeframe="1h")
            if setup:
                all_strats = setup.get('strategies', []).copy()
                if setup.get('primary_strategy'): all_strats.append(setup['primary_strategy'])
                
                is_pdh = any('pdh' in s.lower() or 'pdl' in s.lower() or 'benim' in s.lower() or 'önceki gün' in s.lower() for s in all_strats)
                if is_pdh:
                    matched_coins.append(setup)
                    print(f"🎯 [PDH/PDL UYUMLU] {setup['symbol']} | Yön: {setup['direction']} | Skor: %{setup['confidence_score']}")
                    print(f"   Ana Strateji: {setup['primary_strategy']}")
                    print(f"   Stratejiler: {', '.join(setup['strategies'])}")
                    print(f"   Giriş: ${setup['entry_price']} | SL: ${setup['stop_loss']} | TP1: ${setup['tp1']} | TP2: ${setup['tp2']}")
                    print("-" * 75)

    print(f"\nToplam Taranan: {len(pairs)} | PDH/PDL Filtresine Gerçekten Uyan: {len(matched_coins)} Coin")
    print("ALL LIVE FILTER TESTS COMPLETED!")

if __name__ == "__main__":
    asyncio.run(test_live_pdh_filter())
