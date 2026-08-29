import datetime
from engine.market_data import market_manager

df_15m = market_manager.get_market_data('AAVE/USDT', timeframe='15m', limit=10)
print('--- 15m Mumlari ---')
for _, r in df_15m.iterrows():
    ts = int(r['timestamp'])
    if ts > 1e12: ts = ts // 1000
    dt_utc = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
    dt_local = datetime.datetime.fromtimestamp(ts)
    print(f"UTC: {dt_utc.strftime('%Y-%m-%d %H:%M')} (Yerel: {dt_local.strftime('%H:%M')}) | Open:{r['open']} High:{r['high']} Low:{r['low']} Close:{r['close']} Vol:{r['volume']}")

df_1d = market_manager.get_market_data('AAVE/USDT', timeframe='1d', limit=5)
print('\n--- 1d (Gunluk) Mumlari ---')
for _, r in df_1d.iterrows():
    ts = int(r['timestamp'])
    if ts > 1e12: ts = ts // 1000
    dt_utc = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
    print(f"UTC: {dt_utc.strftime('%Y-%m-%d')} | Open:{r['open']} High:{r['high']} Low:{r['low']} Close:{r['close']} Vol:{r['volume']}")
