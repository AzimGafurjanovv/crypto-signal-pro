import asyncio
from app import get_strategy_backtest

async def test():
    print("=== TESTING 12 STRATEGIES & TP1/TP2/TP3 WIN RATE BREAKDOWN ===")
    res = await get_strategy_backtest("BTC/USDT", "1h", 500)
    print(f"Parite: {res['symbol']} ({res['timeframe']}) | Toplam Test Edilen Strateji: {len(res['leaderboard'])}")
    print("-" * 105)
    print(f"{'Strateji Adı':<45} | {'İşlem':<5} | {'TP1 (%1:1)':<12} | {'TP2 (%1:2)':<12} | {'TP3 (%1:3.5)':<12} | {'Net Kâr':<10}")
    print("-" * 105)
    for s in res['leaderboard']:
        print(f"{s['name']:<45} | {s['total_trades']:<5} | %{s.get('tp1_win_rate', 0):<10} | %{s.get('tp2_win_rate', 0):<10} | %{s.get('tp3_win_rate', 0):<10} | %{s['net_profit_pct']}")
    print("-" * 105)

if __name__ == "__main__":
    asyncio.run(test())
