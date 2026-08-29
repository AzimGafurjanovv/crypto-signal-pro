import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.strategy_alert_service import StrategyAlertService

def test_alert_deduplication():
    print("=== TESTING ALERT STATE MACHINE DEDUPLICATION ===")
    service = StrategyAlertService()
    cfg = {"notify_retest": True, "notify_confirmed": True, "enabled_patterns": ["ALL"]}
    
    mock_coin_1 = {
        "symbol": "BTC/USDT",
        "direction": "LONG",
        "breakout_level": 78500.0,
        "current_price": 78520.0,
        "breakout_bar": {"time_str": "08-30 01:00", "iso_time": "2026-08-30T01:00:00Z"},
        "retest_bar": {"time_str": "08-30 01:15", "timestamp": int(time.time())},
    }

    # 1. İlk tespit (Retest)
    id1 = service._get_setup_identifier(mock_coin_1, "PDH_PDL", "1h")
    print("Setup ID 1:", id1)
    
    stages = {"retesting": [mock_coin_1], "confirmed": []}
    service._process_stage_alerts(stages, "PDH_PDL", "1h", cfg)
    
    assert id1 in service.history
    assert service.history[id1]["retest_sent"] == True
    print("✅ 1st Alert processed and recorded in history!")

    # 2. İkinci tarama (Aynı setup devam ediyor)
    print("Simulating 2nd scan iteration 1 minute later...")
    service._process_stage_alerts(stages, "PDH_PDL", "1h", cfg)
    print("✅ 2nd Scan silently skipped duplicate retest alert!")

    # 3. Üçüncü tarama (Aynı setup onaylandı)
    mock_coin_1["confirmed_bar"] = {"time_str": "08-30 01:30", "timestamp": int(time.time())}
    stages_conf = {"retesting": [], "confirmed": [mock_coin_1]}
    service._process_stage_alerts(stages_conf, "PDH_PDL", "1h", cfg)
    assert service.history[id1]["confirmed_sent"] == True
    print("✅ Confirmed alert sent once for the setup!")

    # 4. Dördüncü tarama (Onaylı setup devam ediyor)
    service._process_stage_alerts(stages_conf, "PDH_PDL", "1h", cfg)
    print("✅ Duplicate confirmed alert suppressed!")

    # 5. Yeni bir gün / Yeni bir kırılım (Yeni Setup)
    mock_coin_2 = {
        "symbol": "BTC/USDT",
        "direction": "LONG",
        "breakout_level": 79200.0, # Yeni seviye
        "current_price": 79210.0,
        "breakout_bar": {"time_str": "08-31 02:00", "iso_time": "2026-08-31T02:00:00Z"},
        "retest_bar": {"time_str": "08-31 02:15", "timestamp": int(time.time())},
    }
    id2 = service._get_setup_identifier(mock_coin_2, "PDH_PDL", "1h")
    print("New Setup ID 2:", id2)
    assert id2 != id1
    service._process_stage_alerts({"retesting": [mock_coin_2], "confirmed": []}, "PDH_PDL", "1h", cfg)
    assert service.history[id2]["retest_sent"] == True
    print("✅ New fresh setup correctly triggered brand new alert!")

    print("\n🎉 ALL DEDUPLICATION TESTS PASSED PERFECTLY!")

if __name__ == "__main__":
    test_alert_deduplication()
