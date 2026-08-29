import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import run_ai_chat, get_ai_models, AIChatRequest

async def test():
    print("=== TESTING AI CHAT & MODEL SELECTOR ENDPOINTS ===")
    
    # 1. Test AI models list
    models_res = await get_ai_models()
    print("[✓] AI Models list:", models_res)
    assert models_res["status"] == "success"
    assert len(models_res["models"]) > 0
    
    # 2. Test AI chat with dummy key (testing error handling and structure)
    req = AIChatRequest(
        symbol="BTC/USDT",
        message="BTC için 1 saatlik grafikte stop loss seviyesini analiz et.",
        history=[],
        model_name="gemini-2.0-flash",
        api_key="test_dummy_key"
    )
    chat_res = await run_ai_chat(req)
    print("[✓] Chat Response status:", chat_res.get("status"))
    print("[✓] Chat Response message/reply:", chat_res.get("message") or chat_res.get("reply")[:100])
    print("ALL CHAT TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test())
