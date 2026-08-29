import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import get_backtest_results

async def run_test():
    res = await get_backtest_results("BTC/USDT", timeframe="1h", limit=500)
    print("Status:", res.get("status"))
    champ = res.get("champion_strategy")
    print("Champion Strategy:", champ["name"] if champ else "None")
    print("Leaderboard Count:", len(res.get("leaderboard", [])))

if __name__ == "__main__":
    asyncio.run(run_test())
