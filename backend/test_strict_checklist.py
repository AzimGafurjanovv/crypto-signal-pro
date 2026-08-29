"""
Test strict chronological confirmation and checklist generator
"""
import sys
import os
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.market_data import market_manager

def test_strict_pdh_pdl(symbol: str, df: pd.DataFrame, timeframe: str = "1h"):
    if df is None or len(df) < 30:
        return None

    n = len(df)
    current_price = float(df['close'].iloc[-1])
    
    # 24 Saatlik Dilimler
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

    curr_len = len(curr_slice)
    if curr_len < 3:
        return None

    # Kronolojik Bar Taraması
    # Her barın verilerini hazırla
    bars = []
    for idx, (orig_idx, row) in enumerate(curr_slice.iterrows()):
        ts = int(row['timestamp']) if 'timestamp' in row else 0
        if ts > 1e12: ts = ts // 1000
        time_str = datetime.fromtimestamp(ts).strftime("%H:%M") if ts > 0 else f"Bar #{idx}"
        bars.append({
            'idx': idx,
            'orig_idx': orig_idx,
            'time': ts,
            'time_str': time_str,
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row.get('volume', 0.0))
        })

    # 🟢 1. LONG (PDH Breakout -> Retest -> Confirmation)
    # A. Kırılım Barını Bul
    breakout_bar = None
    for b in bars:
        if b['close'] > pdh:
            breakout_bar = b
            break

    if breakout_bar:
        bo_idx = breakout_bar['idx']
        post_bo_bars = bars[bo_idx+1:]
        
        # B. Retest Barını Bul (Kırılımdan sonra PDH çizgisine geri çekilen bar)
        retest_bar = None
        for b in post_bo_bars:
            if b['low'] <= (pdh * 1.006) and b['close'] >= (pdh * 0.994):
                retest_bar = b
                break

        # C. Onay Barı (Retest barının kendisi VEYA hemen sonraki 1 bar)
        confirmed_bar = None
        conf_type = ""
        conf_detail = ""

        if retest_bar:
            rt_idx = retest_bar['idx']
            # Aday onay barları: Retest barı veya hemen sonraki bar
            candidate_bars = [b for b in bars if b['idx'] in [rt_idx, rt_idx + 1]]
            
            for c_bar in candidate_bars:
                c, o, h, l = c_bar['close'], c_bar['open'], c_bar['high'], c_bar['low']
                rng = h - l if h > l else 0.0001
                lower_wick = min(o, c) - l
                
                # Formasyon 1: Pin Bar / Hammer (Alt fitil >= %35, Yeşil ve PDH üstü kapanış)
                if c >= o and c > pdh and (lower_wick / rng) >= 0.35 and l <= (pdh * 1.006):
                    confirmed_bar = c_bar
                    conf_type = "Pin Bar / Hammer Rejection"
                    conf_detail = f"Alt fitil: %{lower_wick/rng*100:.0f} ile PDH ($ {pdh:,.4f}) seviyesinden alış tepkisi aldı ve yeşil kapandı."
                    break
                # Formasyon 2: Bullish Engulfing (Önceki barı yutan yeşil itki mumu)
                elif c_bar['idx'] > bo_idx:
                    prev_b = bars[c_bar['idx'] - 1]
                    if c > o and c > prev_b['high'] and c > pdh and (c - o) >= (rng * 0.55):
                        confirmed_bar = c_bar
                        conf_type = "Bullish Engulfing (Yutan Boğa)"
                        conf_detail = f"Önceki barın tepesini (${prev_b['high']:,.4f}) yukarı kırarak PDH üstünde güçlü yeşil gövde kapattı."
                        break

        # Tazelik Kontrolü: Onay mumu SON 2 BAR içinde mi gerçekleşti?
        is_fresh_confirmation = False
        if confirmed_bar:
            if confirmed_bar['idx'] >= (curr_len - 2) and current_price >= (pdh * 0.995) and current_price <= (pdh * 1.025):
                is_fresh_confirmation = True

        # Checklist Oluştur
        checklist = [
            {
                'title': '1. Dünkü Zirve (PDH) Belirlendi',
                'passed': True,
                'detail': f'Dünün en yüksek seviyesi: ${pdh:,.4f}'
            },
            {
                'title': '2. PDH Seviyesi Yukarı Kırıldı',
                'passed': breakout_bar is not None,
                'detail': f"Saat {breakout_bar['time_str']} barında ${breakout_bar['close']:,.4f} ile kırılım kapandı." if breakout_bar else "Henüz PDH üzerinde kapanış yok."
            },
            {
                'title': '3. Seviyeye Retest Yapıldı',
                'passed': retest_bar is not None,
                'detail': f"Saat {retest_bar['time_str']} barında fiyat ${retest_bar['low']:,.4f} seviyesine geri çekilerek PDH test edildi." if retest_bar else "Retest henüz gerçekleşmedi."
            },
            {
                'title': '4. Katı Onay Mumu Kapandı (Anlık & Taze)',
                'passed': is_fresh_confirmation,
                'detail': f"Saat {confirmed_bar['time_str']} barında {conf_type} onaylandı: {conf_detail}" if is_fresh_confirmation else ("Onay mumu henüz oluşmadı veya bayatladı." if confirmed_bar else "Onay mumu bekleniyor.")
            }
        ]

        if is_fresh_confirmation:
            stage = "CONFIRMED"
        elif retest_bar and current_price >= (pdh * 0.992) and current_price <= (pdh * 1.015):
            stage = "RETESTING"
        elif current_price > pdh:
            stage = "BREAKOUT"
        else:
            stage = "INVALIDATED"

        return {
            'symbol': symbol,
            'direction': 'LONG',
            'stage': stage,
            'pdh': pdh,
            'pdl': pdl,
            'current_price': current_price,
            'breakout_bar': breakout_bar,
            'retest_bar': retest_bar,
            'confirmed_bar': confirmed_bar if is_fresh_confirmation else None,
            'checklist': checklist
        }

    # 🔴 2. SHORT (PDL Breakdown -> Retest -> Confirmation)
    breakout_bar = None
    for b in bars:
        if b['close'] < pdl:
            breakout_bar = b
            break

    if breakout_bar:
        bo_idx = breakout_bar['idx']
        post_bo_bars = bars[bo_idx+1:]
        
        retest_bar = None
        for b in post_bo_bars:
            if b['high'] >= (pdl * 0.994) and b['close'] <= (pdl * 1.006):
                retest_bar = b
                break

        confirmed_bar = None
        conf_type = ""
        conf_detail = ""

        if retest_bar:
            rt_idx = retest_bar['idx']
            candidate_bars = [b for b in bars if b['idx'] in [rt_idx, rt_idx + 1]]
            
            for c_bar in candidate_bars:
                c, o, h, l = c_bar['close'], c_bar['open'], c_bar['high'], c_bar['low']
                rng = h - l if h > l else 0.0001
                upper_wick = h - max(o, c)
                
                # Formasyon 1: Shooting Star (Üst fitil >= %35, Kırmızı ve PDL altı kapanış)
                if c <= o and c < pdl and (upper_wick / rng) >= 0.35 and h >= (pdl * 0.994):
                    confirmed_bar = c_bar
                    conf_type = "Shooting Star Rejection"
                    conf_detail = f"Üst fitil: %{upper_wick/rng*100:.0f} ile PDL (${pdl:,.4f}) seviyesinden satıcı tepkisi aldı ve kırmızı kapandı."
                    break
                # Formasyon 2: Bearish Engulfing (Önceki barı yutan kırmızı itki mumu)
                elif c_bar['idx'] > bo_idx:
                    prev_b = bars[c_bar['idx'] - 1]
                    if c < o and c < prev_b['low'] and c < pdl and (o - c) >= (rng * 0.55):
                        confirmed_bar = c_bar
                        conf_type = "Bearish Engulfing (Yutan Ayı)"
                        conf_detail = f"Önceki barın dibini (${prev_b['low']:,.4f}) aşağı kırarak PDL altında güçlü kırmızı gövde kapattı."
                        break

        is_fresh_confirmation = False
        if confirmed_bar:
            if confirmed_bar['idx'] >= (curr_len - 2) and current_price <= (pdl * 1.005) and current_price >= (pdl * 0.975):
                is_fresh_confirmation = True

        checklist = [
            {
                'title': '1. Dünkü Dip (PDL) Belirlendi',
                'passed': True,
                'detail': f'Dünün en düşük seviyesi: ${pdl:,.4f}'
            },
            {
                'title': '2. PDL Seviyesi Aşağı Kırıldı',
                'passed': breakout_bar is not None,
                'detail': f"Saat {breakout_bar['time_str']} barında ${breakout_bar['close']:,.4f} ile kırılım kapandı." if breakout_bar else "Henüz PDL altında kapanış yok."
            },
            {
                'title': '3. Seviyeye Retest Yapıldı',
                'passed': retest_bar is not None,
                'detail': f"Saat {retest_bar['time_str']} barında fiyat ${retest_bar['high']:,.4f} seviyesine geri teperek PDL test edildi." if retest_bar else "Retest henüz gerçekleşmedi."
            },
            {
                'title': '4. Katı Onay Mumu Kapandı (Anlık & Taze)',
                'passed': is_fresh_confirmation,
                'detail': f"Saat {confirmed_bar['time_str']} barında {conf_type} onaylandı: {conf_detail}" if is_fresh_confirmation else ("Onay mumu henüz oluşmadı veya bayatladı." if confirmed_bar else "Onay mumu bekleniyor.")
            }
        ]

        if is_fresh_confirmation:
            stage = "CONFIRMED"
        elif retest_bar and current_price <= (pdl * 1.008) and current_price >= (pdl * 0.985):
            stage = "RETESTING"
        elif current_price < pdl:
            stage = "BREAKOUT"
        else:
            stage = "INVALIDATED"

        return {
            'symbol': symbol,
            'direction': 'SHORT',
            'stage': stage,
            'pdh': pdh,
            'pdl': pdl,
            'current_price': current_price,
            'breakout_bar': breakout_bar,
            'retest_bar': retest_bar,
            'confirmed_bar': confirmed_bar if is_fresh_confirmation else None,
            'checklist': checklist
        }

    return None

if __name__ == "__main__":
    test_coins = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'DOGE/USDT', 'ADA/USDT', 'LINK/USDT', 'SUI/USDT', 'TIA/USDT']
    print("=== TESTING STRICT FRESH CONFIRMATION & CHECKLIST ===")
    for sym in test_coins:
        df = market_manager.get_market_data(sym, timeframe="1h", limit=120)
        res = test_strict_pdh_pdl(sym, df, timeframe="1h")
        if res:
            print(f"\n📌 {res['symbol']} | Yön: {res['direction']} | Aşama: {res['stage']} | Fiyat: ${res['current_price']}")
            for chk in res['checklist']:
                status_icon = "✅" if chk['passed'] else "❌"
                print(f"   {status_icon} {chk['title']}: {chk['detail']}")
