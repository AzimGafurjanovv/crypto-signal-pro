import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.backtest_engine import run_strategy_backtest
from engine.market_data import market_manager

def test_backtest_markers():
    print("=== TESTING BACKTEST TRADE METADATA & MARKERS ===")
    df = market_manager.get_market_data("BTC/USDT", timeframe="1h", limit=500)
    report = run_strategy_backtest("BTC/USDT", df, timeframe="1h")
    
    print("Backtest Leaderboard top 3:")
    for lb in report['leaderboard'][:3]:
        print(f"  • {lb['name']}: {lb['total_trades']} trades | Win Rate: %{lb['win_rate']} | TP1: %{lb.get('tp1_win_rate', 0)} | TP2: %{lb.get('tp2_win_rate', 0)}")

    champ_trades = report['champion_strategy']['recent_trades']
    print(f"\nChampion Strategy ({report['champion_strategy']['name']}) has {len(champ_trades)} recent trades.")
    if champ_trades:
        first_trade = champ_trades[0]
        print("First Trade Sample:")
        print("  Direction:", first_trade['direction'])
        print("  Entry Price:", first_trade['entry_price'], "at time:", first_trade['entry_time'])
        print("  Exit Price:", first_trade['exit_price'], "at time:", first_trade['exit_time'], "Reason:", first_trade['exit_reason'])
        print("  Timestamps: Entry =", first_trade.get('entry_timestamp'), "Exit =", first_trade.get('exit_timestamp'), "Breakout =", first_trade.get('breakout_timestamp'), "Retest =", first_trade.get('retest_timestamp'))
        print("  Lines:", len(first_trade.get('lines', [])))
        for l in first_trade.get('lines', []):
            print(f"    - {l['name']}: ${l['price']} ({l['color']})")

if __name__ == "__main__":
    test_backtest_markers()
