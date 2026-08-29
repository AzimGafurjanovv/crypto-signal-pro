import sys
sys.path.insert(0, 'C:/Users/MR/.gemini/antigravity/scratch/crypto-signal-pro/backend')
from engine.market_data import market_manager
from engine.setup_calculator import calculate_crypto_setup, LAYER_WEIGHTS
from engine.ai_prompt_generator import generate_ai_prompt

print("=== 1. SUPER TRADER KATMANLI KONFLUENS MATRİSİ ===")
print("Toplam Katman Ağırlığı Puanı:", sum(LAYER_WEIGHTS.values()))
for k, v in LAYER_WEIGHTS.items():
    print(f"  - {k}: {v} puan")

print("\n=== 2. CANLI COIN SUPER TRADER DEĞERLENDİRMESİ ===")
pairs = ["TRX/USDT", "BTC/USDT", "ETH/USDT", "SOL/USDT"]
for sym in pairs:
    df = market_manager.get_market_data(sym, timeframe='1h', limit=160)
    if df is not None:
        setup = calculate_crypto_setup(sym, df, timeframe='1h', mtf_data=None)
        if setup:
            print(f"📌 {setup['symbol']} | {setup['direction_label']} | Konfluens Skoru: %{setup['confidence_score']} ({setup['score_grade']}) | R:R: 1:{setup['rr_ratio']}")
            print(f"   Stratejiler: {', '.join(setup['strategies'])}")
            print(f"   Destekler: {[s['name'] + ' ($' + str(round(s['price'], 4)) + ')' for s in setup['supports'][:2]]}")
            print(f"   Dirençler: {[r['name'] + ' ($' + str(round(r['price'], 4)) + ')' for r in setup['resistances'][:2]]}")
            print("-" * 75)

            if sym == "TRX/USDT":
                setup['ai_prompt'] = generate_ai_prompt(setup)
                print("\n=== 3. METİNSEL GRAFİK RESMİ VE İSTEM ÖRNEĞİ (TRX/USDT) ===")
                print(setup['ai_prompt'][:1600])
                print("... [İSTEM DEVAMI MEVCUT] ...")
