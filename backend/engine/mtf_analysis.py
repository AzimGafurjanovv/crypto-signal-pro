import pandas as pd
from typing import Dict, Any, List, Optional
from .indicators import enrich_all_indicators
from .market_data import market_manager

def analyze_single_timeframe(df: pd.DataFrame) -> Dict[str, Any]:
    """Tek bir zaman dilimindeki trend, momentum ve yön durumunu analiz eder."""
    if df is None or len(df) < 30:
        return {'trend': 'NÖTR', 'signal': 'NÖTR', 'signal_label': '⚪ NÖTR', 'rsi': 50.0, 'supertrend': 'NÖTR', 'current_price': 0.0, 'ema50': 0.0, 'ema200': 0.0, 'desc': 'Yetersiz veri'}
        
    df = enrich_all_indicators(df)
    current_price = float(df['close'].iloc[-1])
    rsi = float(df['rsi'].iloc[-1])
    ema20 = float(df['ema_20'].iloc[-1])
    ema50 = float(df['ema_50'].iloc[-1])
    ema200 = float(df['ema_200'].iloc[-1])
    st_dir = int(df['supertrend_dir'].iloc[-1]) # 1 = Bull, -1 = Bear
    
    score = 0
    
    # EMA Değerlendirmesi
    if current_price > ema50 and ema50 > ema200:
        score += 2
        trend = "GÜÇLÜ BOĞA"
    elif current_price > ema20:
        score += 1
        trend = "BOĞA"
    elif current_price < ema50 and ema50 < ema200:
        score -= 2
        trend = "GÜÇLÜ AYI"
    elif current_price < ema20:
        score -= 1
        trend = "AYI"
    else:
        trend = "YATAY / NÖTR"
        
    # Supertrend
    if st_dir == 1:
        score += 1
    else:
        score -= 1
        
    # RSI
    if rsi < 35:
        score += 1 # Aşırı satım tepkisi
    elif rsi > 65:
        score -= 1 # Aşırı alım düzeltmesi
        
    if score >= 2:
        signal = "LONG"
        signal_label = "🟢 LONG"
        desc = f"EMA ve Supertrend boğa yönlü, RSI: {rsi:.1f}"
    elif score <= -2:
        signal = "SHORT"
        signal_label = "🔴 SHORT"
        desc = f"EMA ve Supertrend ayı yönlü, RSI: {rsi:.1f}"
    else:
        signal = "NÖTR"
        signal_label = "⚪ NÖTR"
        desc = f"Kararsız bölge, RSI: {rsi:.1f}"
        
    return {
        'trend': trend,
        'signal': signal,
        'signal_label': signal_label,
        'rsi': round(rsi, 1),
        'supertrend': 'BOĞA' if st_dir == 1 else 'AYI',
        'current_price': current_price,
        'ema50': round(ema50, 4),
        'ema200': round(ema200, 4),
        'desc': desc
    }

def analyze_all_timeframes(symbol: str) -> Dict[str, Any]:
    """
    15m (Kısa Vade / Scalp), 1h (Orta Vade / Gün İçi), 4h (Uzun Vade / Swing) ve 1d (Makro Trend)
    zaman dilimlerini analiz ederek ağırlıklı çoklu zaman dilimi uyumunu hesaplar.
    Makro (1d, 4h) zaman dilimleri mikro (15m) dilimlere göre daha yüksek ağırlığa sahiptir.
    """
    timeframes = ['15m', '1h', '4h', '1d']
    tf_weights = {'15m': 1, '1h': 2, '4h': 3, '1d': 4}  # Toplam 10 ağırlık
    tf_results = {}
    
    total_long_weight = 0
    total_short_weight = 0
    
    for tf in timeframes:
        try:
            df = market_manager.get_market_data(symbol, timeframe=tf, limit=120)
            res = analyze_single_timeframe(df)
            tf_results[tf] = res
            
            w = tf_weights[tf]
            if res['signal'] == 'LONG':
                total_long_weight += w
            elif res['signal'] == 'SHORT':
                total_short_weight += w
        except Exception:
            tf_results[tf] = analyze_single_timeframe(None)
        
    # Zaman Dilimi Uyumunu Ağırlıklı Hesapla (Max 10)
    signals = [tf_results[tf]['signal'] for tf in timeframes]
    long_count = signals.count('LONG')
    short_count = signals.count('SHORT')
    
    is_1d_short = tf_results['1d']['signal'] == 'SHORT'
    is_1d_long = tf_results['1d']['signal'] == 'LONG'
    
    if total_long_weight >= 9:
        alignment_status = "🟢 TAM BOĞA UYUMU (4/4 TF LONG)"
        bias = "LONG"
        bias_strength = "ÇOK GÜÇLÜ"
        summary_tr = "Kısa, orta, uzun ve günlük makro vadelerin tümü alıcı kontrolünde; en yüksek başarı oranlı trend yönü."
    elif total_long_weight >= 6 and not is_1d_short:
        alignment_status = "🟢 GÜÇLÜ BOĞA UYUMU (Makro & Orta Vade Boğa)"
        bias = "LONG"
        bias_strength = "GÜÇLÜ"
        summary_tr = "Makro (1d/4h) ve orta vade alıcı kontrolünde yükseliş trendinde ilerliyor."
    elif total_short_weight >= 9:
        alignment_status = "🔴 TAM AYI UYUMU (4/4 TF SHORT)"
        bias = "SHORT"
        bias_strength = "ÇOK GÜÇLÜ"
        summary_tr = "Kısa, orta, uzun ve günlük makro vadelerin tümü satıcı kontrolünde; en yüksek başarı oranlı düşüş trendi."
    elif total_short_weight >= 6 and not is_1d_long:
        alignment_status = "🔴 GÜÇLÜ AYI UYUMU (Makro & Orta Vade Ayı)"
        bias = "SHORT"
        bias_strength = "GÜÇLÜ"
        summary_tr = "Makro (1d/4h) ve orta vade satıcı kontrolünde düşüş trendinde ilerliyor."
    elif is_1d_short and tf_results['15m']['signal'] == 'LONG':
        alignment_status = "⚠️ TEPKİ YÜKSELİŞİ (Makro Ayı / Kısa Vade Long Tepkisi)"
        bias = "LONG_PULLBACK"
        bias_strength = "ORTA / DÜZELTME (Yüksek Risk)"
        summary_tr = "1D Ana trend düşüş yönlü; 15m yükselişi sadece bir düzeltme/tepki hareketidir. Sıkı stoplu scalp gerekir."
    elif is_1d_long and tf_results['15m']['signal'] == 'SHORT':
        alignment_status = "⚠️ BOĞA DÜZELTMESİ (Makro Boğa / Kısa Vade Kâr Satışı)"
        bias = "SHORT_PULLBACK"
        bias_strength = "ORTA / DÜZELTME (Yüksek Risk)"
        summary_tr = "1D Ana trend yükseliş yönlü; 15m düşüşü kâr satışı geri çekilmesidir."
    else:
        alignment_status = "⚪ KARIŞIK / NÖTR PİYASA YAPISI"
        bias = "NEUTRAL"
        bias_strength = "ZAYIF"
        summary_tr = "Zaman dilimleri arasında yön ayrışması var; destek/direnç kırılımları beklenmeli."
        
    return {
        'symbol': symbol,
        'alignment_status': alignment_status,
        'bias': bias,
        'bias_strength': bias_strength,
        'summary_tr': summary_tr,
        'total_long_weight': total_long_weight,
        'total_short_weight': total_short_weight,

        'timeframes': {
            '15m': {
                'name': 'Kısa Vade (15m - Scalp)',
                'signal': tf_results['15m']['signal_label'],
                'trend': tf_results['15m']['trend'],
                'rsi': tf_results['15m']['rsi'],
                'desc': tf_results['15m']['desc']
            },
            '1h': {
                'name': 'Orta Vade (1h - Gün İçi)',
                'signal': tf_results['1h']['signal_label'],
                'trend': tf_results['1h']['trend'],
                'rsi': tf_results['1h']['rsi'],
                'desc': tf_results['1h']['desc']
            },
            '4h': {
                'name': 'Uzun Vade (4h - Swing)',
                'signal': tf_results['4h']['signal_label'],
                'trend': tf_results['4h']['trend'],
                'rsi': tf_results['4h']['rsi'],
                'desc': tf_results['4h']['desc']
            },
            '1d': {
                'name': 'Makro Vade (1d - Günlük Trend)',
                'signal': tf_results['1d']['signal_label'],
                'trend': tf_results['1d']['trend'],
                'rsi': tf_results['1d']['rsi'],
                'desc': tf_results['1d']['desc']
            }
        }
    }
