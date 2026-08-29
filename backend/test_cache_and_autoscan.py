import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import get_latest_cached_setups, set_auto_scan_config, AutoScanConfigRequest, bg_scanner

async def test():
    print("=== TESTING ARKA PLAN OTOMATİK TARAMA & ÖNBELLEK ENDPOINTS ===")
    
    # 1. Test set auto-scan config
    res_cfg = await set_auto_scan_config(AutoScanConfigRequest(interval_minutes=3))
    print("[✓] Auto-scan config response:", res_cfg)
    assert res_cfg["interval_minutes"] == 3
    
    # 2. Test get latest cached setups
    print("Fetching latest cached setups...")
    res_latest = await get_latest_cached_setups()
    print("[✓] Latest setups status:", res_latest.get("status"))
    print("[✓] Setups count:", len(res_latest.get("setups", [])))
    print("[✓] Last scan time:", res_latest.get("last_scan_time"))
    print("[✓] Next scan in seconds:", res_latest.get("next_scan_seconds"))
    print("[✓] Stats:", res_latest.get("stats"))
    assert len(res_latest.get("setups", [])) > 0
    print("ALL CACHE TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test())
