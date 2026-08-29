import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import run_ai_analysis, AIAnalyzeRequest

async def test():
    print("Testing /api/ai-analyze/NEAR/USDT with dummy key...")
    req = AIAnalyzeRequest(timeframe="1h", api_key="dummy_key_for_testing")
    res = await run_ai_analysis("NEAR/USDT", req)
    print("Response Status:", res.get("status"))
    print("Response Code / Message:", res.get("code"), res.get("message") or res.get("analysis", {}).get("verdict"))

if __name__ == "__main__":
    asyncio.run(test())
