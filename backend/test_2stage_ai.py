import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.market_data import market_manager
from engine.setup_calculator import calculate_crypto_setup
from engine.ai_prompt_generator import generate_ai_prompt

def test_prompt():
    print("=== 2 AŞAMALI AI İSTEM TESTİ ===")
    df = market_manager.get_market_data("BTC/USDT", timeframe="1h", limit=50)
    setup = calculate_crypto_setup("BTC/USDT", df, timeframe="1h", min_confidence=1)
    
    prompt = generate_ai_prompt(setup, df)
    print("\n--- ÜRETİLEN İSTEMİN İLK 600 KARAKTERİ ---")
    print(prompt[:600])
    print("\n[✓] Prompt içinde RAW OHLCV CANDLE LOG mevcut mu?:", "RAW OHLCV CANDLE LOG" in prompt)
    print("[✓] Prompt içinde TARGET STRATEGY mevcut mu?:", "TARGET STRATEGY" in prompt)

if __name__ == "__main__":
    test_prompt()
