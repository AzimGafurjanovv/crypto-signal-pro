"""
Test script for authentic PDH/PDL Breakout & Retest State Machine
"""
import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.market_data import market_manager

def evaluate_pdh_pdl_precision(symbol: str, df: pd.DataFrame, timeframe: str = "1h"):
    if df is None or len(df) < 30:
        return None

    n = len(df)
    
    # 24 Saatlik Önceki Gün ve Güncel Gün Dilimleri
    if 'timestamp' in df.columns:
        ts_series = df['timestamp'].apply(lambda x: int(x)//1000 if int(x) > 1e12 else int(x))
        last_ts = int(ts_series.iloc[-1])
        sec_24h = 86400
        sec_48h = 172800

        current_day_mask = (ts_series >= (last_ts - sec_24h))
        prev_day_mask = (ts_series < (last_ts - sec_24h)) & (ts_series >= (last_ts - sec_48h))

        prev_day_slice = df[prev_day_mask]
        current_day_slice = df[current_day_mask]
    else:
        prev_day_slice = pd.DataFrame()
        current_day_slice = pd.DataFrame()

    if len(prev_day_slice) >= 4 and len(current_day_slice) >= 4:
        pdh = float(prev_day_slice['high'].max())
        pdl = float(prev_day_slice['low'].min())
        curr_slice = current_day_slice
    else:
        lookback_pd = 24 if n >= 48 else n // 2
        prev_day_slice = df.iloc[-lookback_pd*2 : -lookback_pd]
        pdh = float(prev_day_slice['high'].max())
        pdl = float(prev_day_slice['low'].min())
        curr_slice = df.iloc[-lookback_pd:]

    current_price = float(df['close'].iloc[-1])
    
    # Gün içi barları tara
    # 1. Bullish Analiz (PDH Breakout)
    # A. Kırılım kapanışı var mı?
    breakout_bars_bull = []
    for idx, (orig_idx, row) in enumerate(curr_slice.iterrows()):
        if float(row['close']) > pdh:
            breakout_bars_bull.append(idx)

    # 2. Bearish Analiz (PDL Breakdown)
    breakout_bars_bear = []
    for idx, (orig_idx, row) in enumerate(curr_slice.iterrows()):
        if float(row['close']) < pdl:
            breakout_bars_bear.append(idx)

    curr_len = len(curr_slice)
    
    # -------------------------------------------------------------
    # 🟢 BULLISH PDH ANALİZİ
    # -------------------------------------------------------------
    if breakout_bars_bull:
        first_bo = breakout_bars_bull[0]
        post_bo_slice = curr_slice.iloc[first_bo:]
        
        # Kırılım sonrası oluşan en yüksek tepe
        highest_post_bo = float(post_bo_slice['high'].max())
        
        # Retest Kontrolü: Fiyat PDH bölgesine (PDH * 0.996 <= low <= PDH * 1.008) geri çekildi mi?
        retest_occurred = False
        retest_bar_idx = -1
        
        for idx, (orig_idx, row) in enumerate(post_bo_slice.iterrows()):
            r_low = float(row['low'])
            r_close = float(row['close'])
            if r_low <= (pdh * 1.008) and r_close >= (pdh * 0.994):
                retest_occurred = True
                retest_bar_idx = first_bo + idx
                
        # Onay Mumu Kontrolü: Retest barında veya retestten hemen sonraki 1-2 barda onay mumu kapandı mı?
        is_confirmed = False
        conf_reason = ""
        
        if retest_occurred:
            # Son 3 barı incele
            last_3_bars = curr_slice.iloc[max(0, curr_len - 3):]
            for b_idx, (orig_idx, row) in enumerate(last_3_bars.iterrows()):
                c = float(row['close'])
                o = float(row['open'])
                h = float(row['high'])
                l = float(row['low'])
                candle_range = h - l if h > l else 0.0001
                lower_wick = min(o, c) - l
                
                # Formasyon 1: Hammer / Pinbar Rejection (Alt fitil en az %30, yeşil ve PDH üstü kapanış)
                if c >= o and c > pdh and (lower_wick / candle_range) >= 0.30:
                    is_confirmed = True
                    conf_reason = f"Pin Bar / Hammer Alıcı Reddi (Alt fitil: %{lower_wick/candle_range*100:.0f}, Kapanış: ${c:,.4f} > PDH)"
                    break
                # Formasyon 2: Bullish Engulfing / Yutan Boğa (Yeşil gövde, PDH üstü güçlü kapanış)
                elif c > o and c > (pdh * 1.001) and (c - o) >= (candle_range * 0.55):
                    is_confirmed = True
                    conf_reason = f"Güçlü Boğa İtki Mumu (Kapanış: ${c:,.4f} > PDH, Gövde: %{ (c-o)/candle_range*100:.0f})"
                    break

        # Durum Tayini
        if is_confirmed and current_price >= (pdh * 0.995) and current_price <= (pdh * 1.035):
            return {
                'symbol': symbol,
                'direction': 'LONG',
                'stage': 'CONFIRMED',
                'pdh': pdh,
                'pdl': pdl,
                'current_price': current_price,
                'conf_reason': conf_reason
            }
        elif retest_occurred and current_price >= (pdh * 0.992) and current_price <= (pdh * 1.015):
            return {
                'symbol': symbol,
                'direction': 'LONG',
                'stage': 'RETESTING',
                'pdh': pdh,
                'pdl': pdl,
                'current_price': current_price,
                'conf_reason': "Fiyat PDH çizgisinde destek arıyor, henüz onay mumu kapanmadı."
            }
        elif current_price > pdh:
            return {
                'symbol': symbol,
                'direction': 'LONG',
                'stage': 'BREAKOUT',
                'pdh': pdh,
                'pdl': pdl,
                'current_price': current_price,
                'conf_reason': "Fiyat PDH üzerine çıktı, retest için geri çekilme bekleniyor."
            }

    # -------------------------------------------------------------
    # 🔴 BEARISH PDL ANALİZİ
    # -------------------------------------------------------------
    if breakout_bars_bear:
        first_bo = breakout_bars_bear[0]
        post_bo_slice = curr_slice.iloc[first_bo:]
        
        lowest_post_bo = float(post_bo_slice['low'].min())
        
        # Retest Kontrolü: Fiyat PDL bölgesine (PDL * 0.992 <= high <= PDL * 1.006) geri tepti mi?
        retest_occurred = False
        retest_bar_idx = -1
        
        for idx, (orig_idx, row) in enumerate(post_bo_slice.iterrows()):
            r_high = float(row['high'])
            r_close = float(row['close'])
            if r_high >= (pdl * 0.992) and r_close <= (pdl * 1.006):
                retest_occurred = True
                retest_bar_idx = first_bo + idx
                
        is_confirmed = False
        conf_reason = ""
        
        if retest_occurred:
            last_3_bars = curr_slice.iloc[max(0, curr_len - 3):]
            for b_idx, (orig_idx, row) in enumerate(last_3_bars.iterrows()):
                c = float(row['close'])
                o = float(row['open'])
                h = float(row['high'])
                l = float(row['low'])
                candle_range = h - l if h > l else 0.0001
                upper_wick = h - max(o, c)
                
                # Formasyon 1: Shooting Star / Inverted Pinbar Rejection (Üst fitil en az %30, kırmızı ve PDL altı kapanış)
                if c <= o and c < pdl and (upper_wick / candle_range) >= 0.30:
                    is_confirmed = True
                    conf_reason = f"Shooting Star Satıcı Reddi (Üst fitil: %{upper_wick/candle_range*100:.0f}, Kapanış: ${c:,.4f} < PDL)"
                    break
                # Formasyon 2: Bearish Engulfing / Yutan Ayı (Kırmızı gövde, PDL altı güçlü kapanış)
                elif c < o and c < (pdl * 0.999) and (o - c) >= (candle_range * 0.55):
                    is_confirmed = True
                    conf_reason = f"Güçlü Ayı İtki Mumu (Kapanış: ${c:,.4f} < PDL, Gövde: %{ (o-c)/candle_range*100:.0f})"
                    break

        if is_confirmed and current_price <= (pdl * 1.005) and current_price >= (pdl * 0.965):
            return {
                'symbol': symbol,
                'direction': 'SHORT',
                'stage': 'CONFIRMED',
                'pdh': pdh,
                'pdl': pdl,
                'current_price': current_price,
                'conf_reason': conf_reason
            }
        elif retest_occurred and current_price <= (pdl * 1.008) and current_price >= (pdl * 0.985):
            return {
                'symbol': symbol,
                'direction': 'SHORT',
                'stage': 'RETESTING',
                'pdh': pdh,
                'pdl': pdl,
                'current_price': current_price,
                'conf_reason': "Fiyat PDL çizgisinde direnç arıyor, henüz onay mumu kapanmadı."
            }
        elif current_price < pdl:
            return {
                'symbol': symbol,
                'direction': 'SHORT',
                'stage': 'BREAKOUT',
                'pdh': pdh,
                'pdl': pdl,
                'current_price': current_price,
                'conf_reason': "Fiyat PDL altına indi, retest için yukarı tepki bekleniyor."
            }

    return None

if __name__ == "__main__":
    pairs = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'DOGE/USDT', 'ADA/USDT', 'LINK/USDT', 'SUI/USDT', 'NEAR/USDT', 'AVAX/USDT', 'DOT/USDT']
    print(f"{'COIN':<10} | {'YÖN':<6} | {'AŞAMA':<12} | {'FİYAT':<10} | {'PDH / PDL':<15} | ONAY DETAYI")
    print("-" * 90)
    for sym in pairs:
        df = market_manager.get_market_data(sym, timeframe="1h", limit=120)
        res = evaluate_pdh_pdl_precision(sym, df, timeframe="1h")
        if res:
            levels = f"PDH:${res['pdh']:<7.2f}" if res['direction'] == 'LONG' else f"PDL:${res['pdl']:<7.2f}"
            print(f"{res['symbol']:<10} | {res['direction']:<6} | {res['stage']:<12} | ${res['current_price']:<9.4f} | {levels:<15} | {res['conf_reason']}")
