from datetime import datetime
import pandas as pd
from typing import Dict, Any

def format_raw_market_data(setup: Dict[str, Any], df: pd.DataFrame, candle_limit: int = 30) -> str:
    """
    Kullanıcının seçtiği zaman dilimi, zaman aralığı ve mum sayısına (15, 30, 50, 100, 200) göre
    coin'in ham piyasa mum verilerini (OHLCV) ve teknik değerlerini zaman damgasıyla kopyalar.
    """
    symbol = setup['symbol']
    tf = setup['timeframe']
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    limit = max(5, min(len(df), candle_limit))
    recent_candles = df.tail(limit)
    
    first_ts = int(recent_candles['timestamp'].iloc[0]) // 1000 if 'timestamp' in recent_candles.columns else 0
    last_ts = int(recent_candles['timestamp'].iloc[-1]) // 1000 if 'timestamp' in recent_candles.columns else 0
    
    start_time_str = datetime.fromtimestamp(first_ts).strftime("%Y-%m-%d %H:%M") if first_ts > 0 else "-"
    end_time_str = datetime.fromtimestamp(last_ts).strftime("%Y-%m-%d %H:%M") if last_ts > 0 else "-"
    
    candles_md = []
    for _, row in recent_candles.iterrows():
        ts_val = int(row['timestamp']) // 1000 if 'timestamp' in row else 0
        dt_str = datetime.fromtimestamp(ts_val).strftime("%Y-%m-%d %H:%M") if ts_val > 0 else "-"
        candles_md.append(f"| {dt_str} | {row['open']:.4f} | {row['high']:.4f} | {row['low']:.4f} | {row['close']:.4f} | {row['volume']:.2f} |")
    
    candles_table = "\n".join(candles_md)
    ind = setup['indicators']

    vol_ratio_val = ind.get('volume_ratio', 1.0)
    if vol_ratio_val >= 1.0:
        vol_ratio_str = f"{vol_ratio_val}x (Son 20-Mum Ortalamasının %{int((vol_ratio_val - 1.0) * 100)} Üstünde — Yüksek Hacim)"
    else:
        vol_ratio_str = f"{vol_ratio_val}x (Son 20-Mum Ortalamasının %{int((1.0 - vol_ratio_val) * 100)} Altında — Düşük Hacim)"

    vol_24h_chg = ind.get('volume_24h_change_pct', 0.0)
    vol_24h_str = f"{'+' if vol_24h_chg >= 0 else ''}{vol_24h_chg}% (Önceki 24 Saate Göre Dolar Hacmi {'Artışı' if vol_24h_chg >= 0 else 'Düşüşü'})"
    primary_strat = setup.get('primary_strategy', 'SMC & Trend Analizi')

    raw_data_text = f"""# 📊 HAM PİYASA VE MUM VERİSİ (RAW MARKET DATA)
- **Sembol (Symbol)**: {symbol}
- **Zaman Dilimi (Timeframe)**: {tf}
- **Veri Alma Saati**: {now_str} (Yerel Saat)
- **Kapsanan Zaman Aralığı**: {start_time_str} ➡️ {end_time_str} ({limit} Mum)
- **Güncel Fiyat (Price)**: ${setup['current_price']:,.4f}
- **🎯 EN UYGUN STRATEJİ (BEST SUITED STRATEGY)**: {primary_strat}
- **24s Fiyat Değişimi**: %{ind['price_change_24h']}
- **24s Toplam Hacim**: ${ind['volume_24h_usdt']:,.0f} USDT ({vol_24h_str})

---

## 📈 İNDİKATÖR VE SEVİYE VERİLERİ (INDICATORS & LEVELS)
- **RSI (14)**: {ind['rsi']}
- **ATR (14)**: ${ind['atr']}
- **EMA 20**: ${ind['ema20']:,.4f}
- **EMA 50**: ${ind['ema50']:,.4f}
- **EMA 200**: ${ind['ema200']:,.4f}
- **Supertrend**: {ind['supertrend']}
- **MACD Hist**: {ind['macd_hist']}
- **Anlık Bar Hacim Oranı**: {vol_ratio_str}

---

## 🎯 HESAPLANAN SETUP SEVİYELERİ (TRADE LEVELS)
- **İşlem Yönü (Direction)**: {setup['direction_label']}
- **Giriş (Entry)**: ${setup['entry_price']:,.4f}
- **Stop Loss**: ${setup['stop_loss']:,.4f} (-%{setup['risk_percent']})
- **Hedef 1 (TP1)**: ${setup['tp1']:,.4f} (+%{setup['reward_tp1_percent']})
- **Hedef 2 (TP2)**: ${setup['tp2']:,.4f} (+%{setup['reward_tp2_percent']})
- **Hedef 3 (TP3)**: ${setup['tp3']:,.4f} (+%{setup['reward_tp3_percent']})
- **Konfluens Skoru (Score)**: %{setup['confidence_score']} ({setup.get('score_grade', '')})

---

## 🕯️ KAPSATILAN {limit} MUM TABLOSU (OHLCV CANDLES)
| Tarih / Saat | Açılış (Open) | Yüksek (High) | Düşük (Low) | Kapanış (Close) | Hacim (Volume) |
|---|---|---|---|---|---|
{candles_table}
"""
    return raw_data_text.strip()
