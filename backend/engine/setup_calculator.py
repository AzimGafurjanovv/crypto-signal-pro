from datetime import datetime, timezone
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from .indicators import enrich_all_indicators
from .smc import analyze_smc
from .divergence import detect_rsi_divergences
from .patterns import detect_chart_patterns
from .mtf_analysis import analyze_all_timeframes

# =============================================================================
# SUPER TRADER KATMANLI KONFLUENS MOTORU (100 ÜZERİNDEN AĞIRLIKLI PUANLAMA)
# =============================================================================
LAYER_WEIGHTS = {
    # Katman 1: Trend & Piyasa Yapısı (Max 30)
    'htf_trend_alignment':   12,  # 4h ve 1d ana trend ile tam uyum
    'ema_ribbon_structure':  10,  # Fiyat > EMA20 > EMA50 > EMA200 tam hizalama
    'market_structure_bos':   8,  # BOS (Break of Structure) onaylanmış piyasa yapısı
    'market_structure_choch': 10, # CHoCH (Change of Character) — trend dönüşü konfluensi

    # Katman 2: SMC & Kurumsal Likidite (Max 25)
    'order_block_test':     10,  # Taze Order Block bölgesine temas/retest
    'fvg_imbalance_fill':    9,  # FVG (Fair Value Gap) dengesizlik dolumu ve tepki
    'liquidity_sweep':       6,  # BSL/SSL Likidite temizliği (Sweep & Reclaim)

    # Katman 3: Price Action VE FORMASYONLAR (Max 20)
    'primary_pattern':      12,  # Ana Formasyon (Trend Kırılımı+Retest, S/R Flip, Üçgen, W/M)
    'secondary_pattern':     8,  # İkincil teyit formasyonu / Fibonacci Golden Pocket

    # Katman 4: Momentum & Uyumsuzluk (Max 15)
    'rsi_divergence':       10,  # RSI Pozitif / Negatif Uyumsuzluk
    'volume_surge':          5,  # Hacim patlaması (>1.4x 20-günlük ortalama)

    # Katman 5: R:R & Volatilite Kalitesi (Max 10)
    'high_rr_bonus':         6,  # R:R >= 2.0 bonus puanı
    'supertrend_alignment':  4,  # Supertrend indikatör uyumu
}

DISQUALIFIERS = {
    'htf_resistance_wall':  -18, # Long girerken hemen tepede 4h EMA200 veya 4h Bearish OB olması
    'htf_support_wall':     -18, # Short girerken hemen dipte 4h EMA200 veya 4h Bullish OB olması
    'extreme_counter_rsi':  -15, # Long iken RSI > 72 / Short iken RSI < 28
    'against_macro_trend':  -14, # 1d ve 4h Trend zıt yönde
    'low_volume_breakout':   -8, # Hacimsiz kırılım
}

def _evaluate_super_trader_long(
    df: pd.DataFrame,
    smc_data: Dict[str, Any],
    div_data: Dict[str, Any],
    patterns: List[Dict[str, Any]],
    indicators: Dict[str, Any],
    mtf_data: Optional[Dict[str, Any]]
) -> Tuple[int, List[str], List[str], List[str], List[Dict[str, Any]]]:
    """Super Trader LONG değerlendirmesi."""
    score = 0
    long_reasons = []
    strategies = []
    vetos = []
    supports_resistances = []

    current_price = indicators['current_price']
    current_rsi = indicators['rsi']
    current_atr = indicators['atr']
    ema20 = indicators['ema20']
    ema50 = indicators['ema50']
    ema200 = indicators['ema200']
    vol_ratio = indicators['vol_ratio']

    # --- KATMAN 1: TREND VE PİYASA YAPISI (Max 30) ---
    if current_price > ema50 and ema50 > ema200:
        score += LAYER_WEIGHTS['ema_ribbon_structure']
        strategies.append("EMA Boğa Hizalaması")
        long_reasons.append(f"Fiyat (${current_price:,.4f}) > EMA50 (${ema50:,.4f}) > EMA200 (${ema200:,.4f}) boğa hizalamasında.")
        supports_resistances.append({'type': 'DESTEK', 'name': 'EMA 50', 'price': ema50})
        supports_resistances.append({'type': 'DESTEK', 'name': 'EMA 200', 'price': ema200})
    elif current_price > ema20:
        score += 5
        long_reasons.append(f"Fiyat kısa vadeli EMA20 (${ema20:,.4f}) desteğinin üzerinde.")
        supports_resistances.append({'type': 'DESTEK', 'name': 'EMA 20', 'price': ema20})
    else:
        supports_resistances.append({'type': 'DİRENÇ', 'name': 'EMA 20', 'price': ema20})
        supports_resistances.append({'type': 'DİRENÇ', 'name': 'EMA 50', 'price': ema50})

    bullish_choch = [c for c in smc_data['structure'].get('recent_choch', []) if c['type'] == 'BULLISH_CHOCH']
    if bullish_choch:
        score += LAYER_WEIGHTS['market_structure_choch']
        strategies.append("Bullish CHoCH Trend Dönüşü")
        long_reasons.append(f"Piyasa Karakteri Değişimi (CHoCH): Fiyat ${bullish_choch[0]['broken_level']:,.4f} seviyesini kırarak yeni boğa yapısı başlattı.")
        supports_resistances.append({'type': 'DESTEK', 'name': 'CHoCH Kırılım Desteği', 'price': bullish_choch[0]['broken_level']})

    bullish_bos = [b for b in smc_data['structure']['recent_bos'] if b['type'] == 'BULLISH_BOS']
    if bullish_bos:
        score += LAYER_WEIGHTS['market_structure_bos']
        strategies.append("Bullish BOS Yapı Kırılımı")
        long_reasons.append(f"Piyasa Yapısı (BOS): Fiyat ${bullish_bos[0]['broken_level']:,.4f} direncini kırarak Boğa yapısına geçti.")
        supports_resistances.append({'type': 'DESTEK', 'name': 'BOS Kırılım Desteği', 'price': bullish_bos[0]['broken_level']})

    if mtf_data:
        tfs = mtf_data.get('timeframes', {})
        long_tfs = sum(1 for v in tfs.values() if 'LONG' in v.get('signal', ''))
        if long_tfs == 4:
            score += LAYER_WEIGHTS['htf_trend_alignment']
            long_reasons.append("Çoklu Zaman Dilimi (MTF): 15m, 1h, 4h, 1d TÜM zaman dilimleri Boğa yönünde 4/4 tam uyumlu.")
        elif long_tfs >= 3:
            score += 7
            long_reasons.append(f"Çoklu Zaman Dilimi (MTF): {long_tfs}/4 zaman dilimi Boğa yönünde hizalanmış.")

    # --- KATMAN 2: KURUMSAL LİKİDİTE VE SMC BÖLGELERİ (Max 25) ---
    if smc_data['active_bullish_obs']:
        ob = smc_data['active_bullish_obs'][0]
        score += LAYER_WEIGHTS['order_block_test']
        strategies.append("Bullish Order Block (OB)")
        long_reasons.append(f"Kurumsal Emir Bloğu: Fiyat ${ob['bottom']:,.4f} - ${ob['top']:,.4f} Bullish OB talep bölgesinde tepki alıyor.")
        supports_resistances.append({'type': 'DESTEK', 'name': 'Bullish Order Block Üst', 'price': ob['top']})
        supports_resistances.append({'type': 'DESTEK', 'name': 'Bullish Order Block Alt', 'price': ob['bottom']})

    if smc_data['active_bullish_fvgs']:
        fvg = smc_data['active_bullish_fvgs'][0]
        score += LAYER_WEIGHTS['fvg_imbalance_fill']
        strategies.append("Bullish FVG Dengesizlik")
        long_reasons.append(f"Fair Value Gap (FVG): Fiyat ${fvg['bottom']:,.4f} - ${fvg['top']:,.4f} FVG boşluğunu doldurup alıcı buldu.")
        supports_resistances.append({'type': 'DESTEK', 'name': 'Bullish FVG %50 Denge', 'price': fvg['mid']})

    bullish_sweeps = [s for s in smc_data['structure']['recent_sweeps'] if s['type'] == 'BULLISH_LIQUIDITY_SWEEP']
    if bullish_sweeps:
        score += LAYER_WEIGHTS['liquidity_sweep']
        strategies.append("Likidite Avı (Sweep & Reclaim)")
        long_reasons.append(f"Likidite Avı: ${bullish_sweeps[0]['swept_level']:,.4f} altındaki dip stopları süpürüldü ve alım geldi.")

    # --- KATMAN 3: PRICE ACTION VE FORMASYONLAR (Max 20) ---
    bullish_patterns = [p for p in patterns if p['type'] == 'BULLISH']
    for p in bullish_patterns:
        if p['name'] not in strategies:
            strategies.append(p['name'])
        if p.get('breakout_level'):
            supports_resistances.append({'type': 'DESTEK', 'name': f"{p['name']} Kırılım Desteği", 'price': p['breakout_level']})
        if p.get('target'):
            supports_resistances.append({'type': 'DİRENÇ', 'name': f"{p['name']} Formasyon Hedefi", 'price': p['target']})

    if len(bullish_patterns) >= 1:
        score += LAYER_WEIGHTS['primary_pattern']
        long_reasons.append(f"Grafik Formasyonu: {bullish_patterns[0]['name']} teyit edildi — {bullish_patterns[0]['description']}")
    if len(bullish_patterns) >= 2:
        score += LAYER_WEIGHTS['secondary_pattern']
        long_reasons.append(f"İkincil Formasyon Onayı: {bullish_patterns[1]['name']} ile çifte formasyon konfluensi.")

    # --- KATMAN 4: MOMENTUM & DİVERGENCE (Max 15) ---
    if div_data['bullish_divergence']:
        d = div_data['bullish_divergence']
        score += LAYER_WEIGHTS['rsi_divergence']
        strategies.append("RSI Pozitif Uyumsuzluk")
        long_reasons.append(f"RSI Uyumsuzluğu: {d['name_tr']} tespit edildi (RSI: {d['rsi2']:.1f}). Düşüş ivmesi sonlandı.")

    if vol_ratio >= 1.4:
        score += LAYER_WEIGHTS['volume_surge']
        strategies.append("Hacimli Kırılım")
        long_reasons.append(f"Kurumsal Hacim: Son bar hacmi 20 günlük ortalamanın {vol_ratio:.1f} katı seviyesinde.")

    # --- KATMAN 5: SUPERTREND & R:R KALİTESİ (Max 10) ---
    if indicators['supertrend_dir'] == 1:
        score += LAYER_WEIGHTS['supertrend_alignment']
        long_reasons.append("Supertrend İndikatörü AL (Yeşil) bölgesinde.")

    # --- VETO VE DİSKALİFİYE FİLTRELERİ ---
    if current_rsi > 72:
        score += DISQUALIFIERS['extreme_counter_rsi']
        vetos.append(f"RSI Aşırı Alım Bölgesinde ({current_rsi:.1f} > 72): Tepeden Long alma riski!")

    if vol_ratio < 0.75:
        score += DISQUALIFIERS['low_volume_breakout']
        vetos.append("Anlık mum hacmi zayıf (Son 20 mum ortalamasının %75 altında): Sahte kırılım ihtimali yüksek.")

    if mtf_data:
        htf_4h = mtf_data.get('timeframes', {}).get('4h', {})
        htf_ema200 = float(htf_4h.get('ema200', 0.0))
        if htf_ema200 > 0 and current_price < htf_ema200 and current_price >= htf_ema200 * 0.98:
            score += DISQUALIFIERS['htf_resistance_wall']
            vetos.append(f"4h EMA200 (${htf_ema200:,.4f}) majör direnç duvarının hemen altındayız (%2). Long için yüksek risk!")

        if mtf_data.get('timeframes', {}).get('1d', {}).get('signal') == '🔴 SHORT' and not bullish_sweeps and not div_data['bullish_divergence']:
            score += DISQUALIFIERS['against_macro_trend']
            vetos.append("Günlük (1d) makro trend GÜÇLÜ AYI yönünde; retest veya uyumsuzluk olmadan tepki alımı riskli.")

    return score, long_reasons, strategies, vetos, supports_resistances


def _evaluate_super_trader_short(
    df: pd.DataFrame,
    smc_data: Dict[str, Any],
    div_data: Dict[str, Any],
    patterns: List[Dict[str, Any]],
    indicators: Dict[str, Any],
    mtf_data: Optional[Dict[str, Any]]
) -> Tuple[int, List[str], List[str], List[str], List[Dict[str, Any]]]:
    """Super Trader SHORT değerlendirmesi."""
    score = 0
    short_reasons = []
    strategies = []
    vetos = []
    supports_resistances = []

    current_price = indicators['current_price']
    current_rsi = indicators['rsi']
    current_atr = indicators['atr']
    ema20 = indicators['ema20']
    ema50 = indicators['ema50']
    ema200 = indicators['ema200']
    vol_ratio = indicators['vol_ratio']

    # --- KATMAN 1: TREND VE PİYASA YAPISI (Max 30) ---
    if current_price < ema50 and ema50 < ema200:
        score += LAYER_WEIGHTS['ema_ribbon_structure']
        strategies.append("EMA Ayı Hizalaması")
        short_reasons.append(f"Fiyat (${current_price:,.4f}) < EMA50 (${ema50:,.4f}) < EMA200 (${ema200:,.4f}) ayı hizalamasında.")
        supports_resistances.append({'type': 'DİRENÇ', 'name': 'EMA 50', 'price': ema50})
        supports_resistances.append({'type': 'DİRENÇ', 'name': 'EMA 200', 'price': ema200})
    elif current_price < ema20:
        score += 5
        short_reasons.append(f"Fiyat kısa vadeli EMA20 (${ema20:,.4f}) direncinin altında.")
        supports_resistances.append({'type': 'DİRENÇ', 'name': 'EMA 20', 'price': ema20})
    else:
        supports_resistances.append({'type': 'DESTEK', 'name': 'EMA 20', 'price': ema20})
        supports_resistances.append({'type': 'DESTEK', 'name': 'EMA 50', 'price': ema50})

    bearish_choch = [c for c in smc_data['structure'].get('recent_choch', []) if c['type'] == 'BEARISH_CHOCH']
    if bearish_choch:
        score += LAYER_WEIGHTS['market_structure_choch']
        strategies.append("Bearish CHoCH Trend Dönüşü")
        short_reasons.append(f"Piyasa Karakteri Değişimi (CHoCH): Fiyat ${bearish_choch[0]['broken_level']:,.4f} seviyesini kırarak yeni ayı yapısı başlattı.")
        supports_resistances.append({'type': 'DİRENÇ', 'name': 'CHoCH Kırılım Direnci', 'price': bearish_choch[0]['broken_level']})

    bearish_bos = [b for b in smc_data['structure']['recent_bos'] if b['type'] == 'BEARISH_BOS']
    if bearish_bos:
        score += LAYER_WEIGHTS['market_structure_bos']
        strategies.append("Bearish BOS Yapı Kırılımı")
        short_reasons.append(f"Piyasa Yapısı (BOS): Fiyat ${bearish_bos[0]['broken_level']:,.4f} desteğini kırarak Ayı yapısına geçti.")
        supports_resistances.append({'type': 'DİRENÇ', 'name': 'BOS Kırılım Direnci', 'price': bearish_bos[0]['broken_level']})

    if mtf_data:
        tfs = mtf_data.get('timeframes', {})
        short_tfs = sum(1 for v in tfs.values() if 'SHORT' in v.get('signal', ''))
        if short_tfs == 4:
            score += LAYER_WEIGHTS['htf_trend_alignment']
            short_reasons.append("Çoklu Zaman Dilimi (MTF): 15m, 1h, 4h, 1d TÜM zaman dilimleri Ayı yönünde 4/4 tam uyumlu.")
        elif short_tfs >= 3:
            score += 7
            short_reasons.append(f"Çoklu Zaman Dilimi (MTF): {short_tfs}/4 zaman dilimi Ayı yönünde hizalanmış.")

    # --- KATMAN 2: KURUMSAL LİKİDİTE VE SMC BÖLGELERİ (Max 25) ---
    if smc_data['active_bearish_obs']:
        ob = smc_data['active_bearish_obs'][0]
        score += LAYER_WEIGHTS['order_block_test']
        strategies.append("Bearish Order Block (OB)")
        short_reasons.append(f"Kurumsal Emir Bloğu: Fiyat ${ob['bottom']:,.4f} - ${ob['top']:,.4f} Bearish OB direnç bölgesinden ret yiyor.")
        supports_resistances.append({'type': 'DİRENÇ', 'name': 'Bearish Order Block Üst', 'price': ob['top']})
        supports_resistances.append({'type': 'DİRENÇ', 'name': 'Bearish Order Block Alt', 'price': ob['bottom']})

    if smc_data['active_bearish_fvgs']:
        fvg = smc_data['active_bearish_fvgs'][0]
        score += LAYER_WEIGHTS['fvg_imbalance_fill']
        strategies.append("Bearish FVG Dengesizlik")
        short_reasons.append(f"Fair Value Gap (FVG): Fiyat ${fvg['bottom']:,.4f} - ${fvg['top']:,.4f} FVG direnç boşluğunu doldurup satıcı buldu.")
        supports_resistances.append({'type': 'DİRENÇ', 'name': 'Bearish FVG %50 Denge', 'price': fvg['mid']})

    bearish_sweeps = [s for s in smc_data['structure']['recent_sweeps'] if s['type'] == 'BEARISH_LIQUIDITY_SWEEP']
    if bearish_sweeps:
        score += LAYER_WEIGHTS['liquidity_sweep']
        strategies.append("Likidite Avı (Sweep & Reclaim)")
        short_reasons.append(f"Likidite Avı: ${bearish_sweeps[0]['swept_level']:,.4f} üzerindeki tepe stoplar süpürüldü ve satış geldi.")

    # --- KATMAN 3: PRICE ACTION VE FORMASYONLAR (Max 20) ---
    bearish_patterns = [p for p in patterns if p['type'] == 'BEARISH']
    for p in bearish_patterns:
        if p['name'] not in strategies:
            strategies.append(p['name'])
        if p.get('breakout_level'):
            supports_resistances.append({'type': 'DİRENÇ', 'name': f"{p['name']} Kırılım Direnci", 'price': p['breakout_level']})
        if p.get('target'):
            supports_resistances.append({'type': 'DESTEK', 'name': f"{p['name']} Formasyon Hedefi", 'price': p['target']})

    if len(bearish_patterns) >= 1:
        score += LAYER_WEIGHTS['primary_pattern']
        short_reasons.append(f"Grafik Formasyonu: {bearish_patterns[0]['name']} teyit edildi — {bearish_patterns[0]['description']}")
    if len(bearish_patterns) >= 2:
        score += LAYER_WEIGHTS['secondary_pattern']
        short_reasons.append(f"İkincil Formasyon Onayı: {bearish_patterns[1]['name']} ile çifte formasyon konfluensi.")

    # --- KATMAN 4: MOMENTUM & DİVERGENCE (Max 15) ---
    if div_data['bearish_divergence']:
        d = div_data['bearish_divergence']
        score += LAYER_WEIGHTS['rsi_divergence']
        strategies.append("RSI Negatif Uyumsuzluk")
        short_reasons.append(f"RSI Uyumsuzluğu: {d['name_tr']} tespit edildi (RSI: {d['rsi2']:.1f}). Yükseliş ivmesi sonlandı.")

    if vol_ratio >= 1.4:
        score += LAYER_WEIGHTS['volume_surge']
        strategies.append("Hacimli Kırılım")
        short_reasons.append(f"Kurumsal Hacim: Satış yönlü hacim 20 günlük ortalamanın {vol_ratio:.1f} katı seviyesinde.")

    # --- KATMAN 5: SUPERTREND & R:R KALİTESİ (Max 10) ---
    if indicators['supertrend_dir'] == -1:
        score += LAYER_WEIGHTS['supertrend_alignment']
        short_reasons.append("Supertrend İndikatörü SAT (Kırmızı) bölgesinde.")

    # --- VETO VE DİSKALİFİYE FİLTRELERİ ---
    if current_rsi < 28:
        score += DISQUALIFIERS['extreme_counter_rsi']
        vetos.append(f"RSI Aşırı Satım Bölgesinde ({current_rsi:.1f} < 28): Dipten Short satma riski!")

    if vol_ratio < 0.75:
        score += DISQUALIFIERS['low_volume_breakout']
        vetos.append("Anlık mum hacmi zayıf (Son 20 mum ortalamasının %75 altında): Sahte kırılım ihtimali yüksek.")

    if mtf_data:
        htf_4h = mtf_data.get('timeframes', {}).get('4h', {})
        htf_ema200 = float(htf_4h.get('ema200', 0.0))
        if htf_ema200 > 0 and current_price > htf_ema200 and current_price <= htf_ema200 * 1.02:
            score += DISQUALIFIERS['htf_support_wall']
            vetos.append(f"4h EMA200 (${htf_ema200:,.4f}) majör destek duvarının hemen üzerindeyiz (%2). Short için yüksek risk!")

        if mtf_data.get('timeframes', {}).get('1d', {}).get('signal') == '🟢 LONG' and not bearish_sweeps and not div_data['bearish_divergence']:
            score += DISQUALIFIERS['against_macro_trend']
            vetos.append("Günlük (1d) makro trend GÜÇLÜ BOĞA yönünde; retest veya uyumsuzluk olmadan short riski yüksek.")

    return score, short_reasons, strategies, vetos, supports_resistances


def _get_super_trader_grade(score: int) -> Tuple[str, str]:
    if score >= 85:
        return "🏆 A+ EFSANE SETUP", "Mükemmel konfluens! Tüm katmanlar, SMC ve MTF onaylı."
    elif score >= 70:
        return "🟢 A SINIFI SETUP", "Yüksek başarı olasılığı! Güçlü teknik ve kurumsal onaylar mevcut."
    elif score >= 55:
        return "🟡 B SINIFI SETUP", "Orta derece konfluens. Şartlı ve disiplinli pozisyon yönetimi gerekli."
    elif score >= 40:
        return "🟠 C SINIFI SETUP", "Zayıf teyitler. İşlem riski yüksek."
    return "⚪ ZAYIF / BAŞLANGIÇ SETUP", "Çok düşük güven skoru (%1 - %39)."


def calculate_crypto_setup(
    symbol: str,
    df: pd.DataFrame,
    timeframe: str = "1h",
    mtf_data: Optional[Dict[str, Any]] = None,
    min_confidence: int = 1
) -> Optional[Dict[str, Any]]:

    if len(df) < 50:
        return None

    df = enrich_all_indicators(df)
    smc_data = analyze_smc(df)
    div_data = detect_rsi_divergences(df)
    patterns = detect_chart_patterns(df)

    current_price = float(df['close'].iloc[-1])
    current_rsi  = float(df['rsi'].iloc[-1])
    current_atr  = float(df['atr'].iloc[-1])
    ema20        = float(df['ema_20'].iloc[-1])
    ema50        = float(df['ema_50'].iloc[-1])
    ema200       = float(df['ema_200'].iloc[-1])
    supertrend_dir = int(df['supertrend_dir'].iloc[-1])
    macd_hist    = float(df['macd_hist'].iloc[-1])
    vol_ratio    = float(df['volume_ratio'].iloc[-1])

    indicators = {
        'current_price': current_price,
        'rsi': current_rsi,
        'atr': current_atr,
        'ema20': ema20,
        'ema50': ema50,
        'ema200': ema200,
        'supertrend_dir': supertrend_dir,
        'macd_hist': macd_hist,
        'vol_ratio': vol_ratio
    }

    # Long & Short Değerlendirmesi
    l_score, l_reasons, l_strats, l_vetos, l_sr = _evaluate_super_trader_long(df, smc_data, div_data, patterns, indicators, mtf_data)
    s_score, s_reasons, s_strats, s_vetos, s_sr = _evaluate_super_trader_short(df, smc_data, div_data, patterns, indicators, mtf_data)

    # Net yön tespiti ve yatay piyasa (choppy) filtresi
    score_diff = abs(l_score - s_score)
    max_raw_score = max(l_score, s_score)
    
    # ✅ Çok düşük skor (< 40) veya netlik yoksa (fark < 6 ve skor < 50) iptal
    if max_raw_score < 40:
        return None
    if score_diff < 6 and max_raw_score < 50:
        return None

    is_long = l_score >= s_score
    raw_score = l_score if is_long else s_score
    reasons = l_reasons if is_long else s_reasons
    strategies = l_strats if is_long else s_strats
    vetos = l_vetos if is_long else s_vetos
    sr_levels = l_sr if is_long else s_sr

    confidence_score = max(1, min(99, raw_score))
    
    # Ağır veto durumu: Çoklu diskalifiye varsa skoru ciddi düşür
    if len(vetos) >= 2:
        confidence_score = max(1, confidence_score - 15)

    score_grade, score_desc = _get_super_trader_grade(confidence_score)

    if confidence_score < min_confidence or confidence_score < 35:
        return None

    if not strategies:
        strategies.append("Teknik Konfluens Hizalaması")

    direction_str = "LONG" if is_long else "SHORT"
    direction_label = f"{'🟢' if is_long else '🔴'} {score_grade} ({direction_str})"

    # 🎯 EN UYGUN / BASKIN STRATEJİ BELİRLEME (Gerçek Katalizör Önceliği)
    matching_patterns = [p for p in patterns if (p['type'] == 'BULLISH' if is_long else p['type'] == 'BEARISH')]
    pattern_names = [p['name'] for p in matching_patterns]
    
    dominant_strats = []
    # 1. Teyitli net grafik formasyonu
    if matching_patterns:
        dominant_strats.append(matching_patterns[0]['name'])
    # 2. Kurumsal SMC Order Block / FVG / Likidite
    smc_matches = [s for s in strategies if any(k in s for k in ['Order Block', 'OB', 'FVG', 'Likidite'])]
    if smc_matches:
        dominant_strats.append(smc_matches[0])
    # 3. Piyasa yapısı değişimi (CHoCH / BOS)
    struct_matches = [s for s in strategies if any(k in s for k in ['CHoCH', 'BOS'])]
    if struct_matches:
        dominant_strats.append(struct_matches[0])
    # 4. RSI Uyumsuzluğu
    div_matches = [s for s in strategies if 'Uyumsuzluk' in s]
    if div_matches:
        dominant_strats.append(div_matches[0])
    # 5. EMA Trend
    trend_matches = [s for s in strategies if 'EMA' in s]
    if trend_matches:
        dominant_strats.append(trend_matches[0])

    if dominant_strats:
        primary_strategy = dominant_strats[0]
        if len(dominant_strats) > 1 and dominant_strats[1] != primary_strategy:
            primary_strategy += f" & {dominant_strats[1]}"
    else:
        primary_strategy = strategies[0] if strategies else "Teknik Konfluens Hizalaması"

    # ─────────────────────────────────────────────────────────────────────────
    # 🛑 PROFESYONEL STOP LOSS VE TAKE PROFIT HESAPLAMASI (ATR + Swing Destek/Direnç)
    # Kriptoda %0.8 gibi dar SL'ler piyasa gürültüsünde (noise) kolayca patlar.
    # Doğru yaklaşım: En az 1.5-2.0 x ATR veya yapısal swing dip/tepe arkasına SL koymak.
    # ─────────────────────────────────────────────────────────────────────────
    swing_highs = smc_data['structure']['swing_highs']
    swing_lows  = smc_data['structure']['swing_lows']
    entry_price = current_price
    min_atr_buffer = max(current_atr * 1.6, entry_price * 0.012)  # En az %1.2 veya 1.6x ATR

    if is_long:
        # Swing low bazlı veya ATR bazlı güvenli SL
        struct_sl = swing_lows[-1]['price'] * 0.997 if swing_lows else (entry_price - min_atr_buffer)
        atr_sl = entry_price - min_atr_buffer
        
        # SL'yi yapısal dip ile ATR'ın en mantıklı olanına koy (aşırı uzak veya aşırı yakın olmasın)
        raw_sl = min(struct_sl, atr_sl)
        # Sınırlar: Maksimum %6 risk, minimum %1.2 risk
        stop_loss = max(entry_price * 0.94, min(entry_price - min_atr_buffer, raw_sl))
        
        risk = entry_price - stop_loss
        if risk <= 0:
            risk = min_atr_buffer
            stop_loss = entry_price - risk
            
        tp1 = round(entry_price + risk * 1.5, 4)
        tp2 = round(entry_price + risk * 2.5, 4)
        tp3 = round(entry_price + risk * 4.0, 4)
        rr_ratio = round((tp2 - entry_price) / risk, 2)
        stop_loss = round(stop_loss, 4)
        is_invalidated = False
    else:
        struct_sl = swing_highs[-1]['price'] * 1.003 if swing_highs else (entry_price + min_atr_buffer)
        atr_sl = entry_price + min_atr_buffer
        
        raw_sl = max(struct_sl, atr_sl)
        stop_loss = min(entry_price * 1.06, max(entry_price + min_atr_buffer, raw_sl))
        
        risk = stop_loss - entry_price
        if risk <= 0:
            risk = min_atr_buffer
            stop_loss = entry_price + risk
            
        tp1 = round(entry_price - risk * 1.5, 4)
        tp2 = round(entry_price - risk * 2.5, 4)
        tp3 = round(entry_price - risk * 4.0, 4)
        rr_ratio = round((entry_price - tp2) / risk, 2)
        stop_loss = round(stop_loss, 4)

    if rr_ratio >= 2.0 and confidence_score >= 50:
        confidence_score = min(99, confidence_score + LAYER_WEIGHTS['high_rr_bonus'])
        score_grade, score_desc = _get_super_trader_grade(confidence_score)
        direction_label = f"{'🟢' if is_long else '🔴'} {score_grade} ({direction_str})"

    # Veto veya düşük güven durumunda setup geçersizliği (Invalidated) tespiti
    is_invalidated = bool(len(vetos) >= 2 or confidence_score < 40)

    # Hassas 24 Saatlik Fiyat Değişimi & 24 Saatlik Toplam Hacim Karşılaştırması
    idx_24h = -24 if len(df) >= 24 else -len(df)
    price_24h_ago = float(df['close'].iloc[idx_24h])
    price_change_24h = ((current_price - price_24h_ago) / price_24h_ago) * 100.0

    curr_24h_vol_usdt = float(df['volume'].iloc[-24:].sum() * current_price) if len(df) >= 24 else float(df['volume'].sum() * current_price)
    
    if len(df) >= 48:
        curr_24h_vol = float(df['volume'].iloc[-24:].sum())
        prev_24h_vol = float(df['volume'].iloc[-48:-24].sum())
        vol_24h_change_pct = ((curr_24h_vol - prev_24h_vol) / prev_24h_vol) * 100.0 if prev_24h_vol > 0 else 0.0
    else:
        vol_24h_change_pct = 0.0

    # 24 mumluk (tam 24 saatlik) saf OHLCV tablosu oluştur
    raw_rows = []
    tail_df = df.tail(24)
    for _, row in tail_df.iterrows():
        ts = int(row['timestamp']) if 'timestamp' in row else 0
        if ts > 1e12: ts = ts // 1000
        date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%m-%d %H:%M UTC") if ts > 0 else "N/A"
        o, h, l, c, v = float(row['open']), float(row['high']), float(row['low']), float(row['close']), float(row['volume'])
        candle_dir = "🟢" if c >= o else "🔴"
        body_pct = abs(c - o) / o * 100 if o > 0 else 0
        wick_top = h - max(o, c)
        wick_bot = min(o, c) - l
        raw_rows.append(
            f"{candle_dir} {date_str} | Açılış:${o:,.4f} Yüksek:${h:,.4f} Düşük:${l:,.4f} Kapanış:${c:,.4f} | "
            f"Gövde:%{body_pct:.2f} ÜstFitil:${wick_top:,.4f} AltFitil:${wick_bot:,.4f} | Hacim:{v:,.0f}"
        )
    raw_candles_table = "\n".join(raw_rows)

    supports = sorted([sr for sr in sr_levels if sr['type'] == 'DESTEK'], key=lambda x: x['price'], reverse=True)
    resistances = sorted([sr for sr in sr_levels if sr['type'] == 'DİRENÇ'], key=lambda x: x['price'])

    return {
        'symbol': symbol,
        'timeframe': timeframe,
        'raw_candles_table': raw_candles_table,
        'direction': direction_str,
        'direction_label': direction_label,
        'confidence_score': confidence_score,
        'score_grade': score_grade,
        'score_desc': score_desc,
        'primary_strategy': primary_strategy, # 🎯 En Uygun Strateji
        'rr_ratio': rr_ratio,
        'current_price': current_price,
        'entry_price': entry_price,
        'stop_loss': stop_loss,
        'tp1': tp1,
        'tp2': tp2,
        'tp3': tp3,
        'risk_percent':        round(abs(entry_price - stop_loss) / entry_price * 100.0, 2),
        'reward_tp1_percent':  round(abs(tp1 - entry_price) / entry_price * 100.0, 2),
        'reward_tp2_percent':  round(abs(tp2 - entry_price) / entry_price * 100.0, 2),
        'reward_tp3_percent':  round(abs(tp3 - entry_price) / entry_price * 100.0, 2),
        'strategies': strategies,
        'patterns': pattern_names,
        'reasons': reasons[:6],
        'vetos': vetos,
        'supports': supports,
        'resistances': resistances,
        'is_invalidated': is_invalidated,
        'indicators': {
            'rsi':               round(current_rsi, 1),
            'atr':               round(current_atr, 4),
            'ema20':             round(ema20, 4),
            'ema50':             round(ema50, 4),
            'ema200':            round(ema200, 4),
            'supertrend':        'BULLISH' if supertrend_dir == 1 else 'BEARISH',
            'macd_hist':         round(macd_hist, 4),
            'volume_ratio':      round(vol_ratio, 2),
            'price_change_24h':  round(price_change_24h, 2),
            'volume_24h_change_pct': round(vol_24h_change_pct, 2),
            'volume_24h_usdt':   round(curr_24h_vol_usdt, 0),
        },
        'mtf': mtf_data,
    }
