import sys
import os
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.telegram_notifier import load_telegram_config, save_telegram_config

def test_telegram_config():
    print("=== TESTING TELEGRAM CONFIG ===")
    cfg = load_telegram_config()
    print("Initial Config:", cfg)
    
    cfg["notify_retest"] = True
    cfg["notify_confirmed"] = True
    saved = save_telegram_config(cfg)
    print("Saved:", saved)
    
    loaded = load_telegram_config()
    print("Loaded after save:", loaded)
    assert loaded["notify_retest"] == True
    print("✅ Telegram Config Test Passed!")

if __name__ == "__main__":
    test_telegram_config()
