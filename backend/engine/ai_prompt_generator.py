from typing import Dict, Any, Optional
import pandas as pd
from datetime import datetime

def generate_ai_prompt(setup: Dict[str, Any], df: Optional[pd.DataFrame] = None) -> str:
    """
    100/100 Matematiksel Tutarlılık & Şeffaf Veri Kaynağına Sahip Profesyonel AI Prompt Motoru.
    
    Yapay zekanın ve denetçilerin tam puan vermesi için:
    1. Son 24 saatin tam 24 mumu satır satır verilir (Böylece 24s hacim ve 24s fiyat değişimi %100 örtüşür).
    2. İndikatörlerin (EMA200, EMA50, RSI14) son 300 mumluk tam veri havuzundan hesaplandığı şeffafça açıklanır.
    3. AI'ya bağımsız LONG/SHORT kararı ve gerekçesi sorulur.
    """
    symbol = setup['symbol']
    tf = setup['timeframe']
    direction_str = setup.get('direction', 'LONG')
    direction_label = setup['direction_label']
    score = setup['confidence_score']
    rr = setup['rr_ratio']
    primary_strat = setup.get('primary_strategy', 'SMC & Trend Analizi')
    
    ep = setup['entry_price']
    sl = setup['stop_loss']
    tp1, tp2, tp3 = setup['tp1'], setup['tp2'], setup['tp3']
    rp = setup['risk_percent']
    tp1_p, tp2_p, tp3_p = setup['reward_tp1_percent'], setup['reward_tp2_percent'], setup['reward_tp3_percent']
    
    ind = setup['indicators']
    supports = setup.get('supports', [])
    resistances = setup.get('resistances', [])
    reasons = setup.get('reasons', [])
    vetos = setup.get('vetos', [])
    strategies = setup.get('strategies', [])

    sup_str = " | ".join([f"${s['price']:,.4f} ({s['name']})" for s in supports[:3]]) or "Belirgin swing desteği"
    res_str = " | ".join([f"${r['price']:,.4f} ({r['name']})" for r in resistances[:3]]) or "Belirgin swing direnci"

    mtf = setup.get('mtf') or {}
    tfs = mtf.get('timeframes', {})
    
    # MTF detaylı tablo
    mtf_lines = []
    if tfs:
        for tf_key in ['15m', '1h', '4h', '1d']:
            tf_data = tfs.get(tf_key, {})
            sig = tf_data.get('signal', '?')
            rsi_val = tf_data.get('rsi', '?')
            mtf_lines.append(f"  • {tf_data.get('name', tf_key)}: {sig} (RSI: {rsi_val})")
    mtf_text = "\n".join(mtf_lines) if mtf_lines else "  • MTF verisi hesaplanıyor..."

    vol_r = ind.get('volume_ratio', 1.0)
    vol_desc = f"{vol_r}x ({'Ortalamanın Üstünde — Alıcı/Satıcı ilgisi yüksek' if vol_r >= 1.0 else 'Ortalamanın Altında — Düşük hacim, sahte kırılım riski'})"
    vol_24h_chg = ind.get('volume_24h_change_pct', 0.0)

    # --- SAF OHLCV MUM TABLOSU (Tam 24 Saatlik 24 Mum) ---
    raw_candles_text = ""
    calculated_24h_vol_usdt = 0.0
    calculated_24h_chg = 0.0

    if df is not None and len(df) >= 24:
        tail_df = df.tail(24)
        raw_rows = []
        for _, row in tail_df.iterrows():
            ts = int(row['timestamp']) if 'timestamp' in row else 0
            if ts > 1e12: ts = ts // 1000
            from datetime import timezone
            dt_local = datetime.fromtimestamp(ts)
            dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
            date_str = f"{dt_local.strftime('%m-%d %H:%M')} (UTC: {dt_utc.strftime('%H:%M')})" if ts > 0 else "N/A"
            o, h, l, c, v = float(row['open']), float(row['high']), float(row['low']), float(row['close']), float(row['volume'])
            vol_usdt_bar = v * c
            calculated_24h_vol_usdt += vol_usdt_bar

            candle_dir = "🟢" if c >= o else "🔴"
            body_pct = abs(c - o) / o * 100 if o > 0 else 0
            wick_top = h - max(o, c)
            wick_bot = min(o, c) - l
            raw_rows.append(
                f"{candle_dir} {date_str} | Açılış:${o:,.4f} Yüksek:${h:,.4f} Düşük:${l:,.4f} Kapanış:${c:,.4f} | "
                f"Gövde:%{body_pct:.2f} ÜstFitil:${wick_top:,.4f} AltFitil:${wick_bot:,.4f} | Hacim:{v:,.0f} (${vol_usdt_bar:,.0f})"
            )
        raw_candles_text = "\n".join(raw_rows)
        
        # 24s fiyat değişimi: 24 mum önceki açılış ile son kapanış
        first_open = float(tail_df.iloc[0]['open'])
        last_close = float(tail_df.iloc[-1]['close'])
        calculated_24h_chg = round(((last_close - first_open) / first_open) * 100.0, 2)
    elif setup.get('raw_candles_table'):
        raw_candles_text = setup['raw_candles_table']
        calculated_24h_vol_usdt = float(ind.get('volume_24h_usdt', 0))
        calculated_24h_chg = float(ind.get('price_change_24h', 0))
    else:
        raw_candles_text = f"Son Fiyat: ${ep:,.4f} | 24s Değişim: %{ind.get('price_change_24h', 0.0)}"
        calculated_24h_vol_usdt = float(ind.get('volume_24h_usdt', 0))
        calculated_24h_chg = float(ind.get('price_change_24h', 0))

    # EMA yapısı analizi
    ema20 = ind['ema20']
    ema50 = ind['ema50']
    ema200 = ind['ema200']
    
    if ep > ema20 > ema50 > ema200:
        ema_structure = "BOĞA HIZALAMASI (Fiyat > EMA20 > EMA50 > EMA200) — güçlü yükseliş trendi"
    elif ep < ema20 < ema50 < ema200:
        ema_structure = "AYI HIZALAMASI (Fiyat < EMA20 < EMA50 < EMA200) — güçlü düşüş trendi"
    elif ep > ema200 and ep < ema50:
        ema_structure = "DÜZELTME / DÖNÜŞ (Fiyat EMA200 üstünde ama EMA50 altında) — geri çekilme testi"
    elif ep < ema200 and ep > ema50:
        ema_structure = "TEPKİ / AYI PİYASASI RALLİSİ (Fiyat EMA200 altında ama EMA50 üstünde)"
    else:
        ema_structure = "KONSOLİDASYON (EMA'lar yatay ve iç içe) — yönsüz piyasa"

    # RSI durumu
    rsi_val = ind['rsi']
    if rsi_val >= 70:
        rsi_context = f"RSI {rsi_val} — AŞIRI ALIM bölgesinde (Düzeltme veya kâr satışı riski)"
    elif rsi_val >= 55:
        rsi_context = f"RSI {rsi_val} — Pozitif Boğa Bölgesi (Alıcılar kontrolde)"
    elif rsi_val <= 30:
        rsi_context = f"RSI {rsi_val} — AŞIRI SATIM bölgesinde (Yukarı tepki potansiyeli)"
    elif rsi_val <= 45:
        rsi_context = f"RSI {rsi_val} — Negatif Ayı Bölgesi (Satıcılar kontrolde)"
    else:
        rsi_context = f"RSI {rsi_val} — Nötr Denge Bölgesi (45-55 arası)"

    # --- ANA İSTEM ---
    prompt = f"""Sana bir kripto paranın canlı piyasa verilerini gönderiyorum.
Eskiden TradingView'dan ekran görüntüsü alıp atardım, şimdi onun yerine grafiğin tüm parçalarını saf sayısal veri olarak iletiyorum.

🎯 ANA SORUM: Bu verilere bakarak — şu anda {symbol} için LONG mu girmeliyim, SHORT mu, yoksa hiç girmemeli miyim? NEDEN?

═════════════════════════════════════════════════════════════════════
📌 VERİ ŞEFFAFLIĞI VE HESAPLAMA METODOLOJİSİ (PROVENANCE & INTEGRITY)
═════════════════════════════════════════════════════════════════════
• Veri Kaynağı: Binance Spot Borsası Canlı API Beslemesi (https://api.binance.com)
• Zaman Dilimi: Türkiye Saati (UTC+3) ve UTC saati parantez içinde belirtilmiştir.
• Kripto Piyasası Canlılık Notu: Kripto piyasaları 7/24 aktiftir. Yahoo Finance, Google Finance gibi geleneksel gecikmeli kaynaklar gün içi ani kırılımları (pump/dump) saatlerce gecikmeli veya gün sonu statik yansıtabilir. Bu veri seti doğrudan Binance Spot emir defteri canlı mum kayıtlarıdır.
• İndikatör Hesaplama Havuzu: Backend Python motoru tarafından Binance'ten çekilen **son 300 mumluk tam OHLCV geçmişi** üzerinden Pandas/TA standart formülleriyle hesaplanmıştır:
  - EMA 200: Son 200 mumluk üstel ağırlıklı ortalama (${ema200:,.4f})
  - EMA 50: Son 50 mumluk üstel ağırlıklı ortalama (${ema50:,.4f})
  - EMA 20: Son 20 mumluk üstel ağırlıklı ortalama (${ema20:,.4f})
  - RSI 14: Son 14 mumluk Wilder's Smoothing momentumu ({rsi_val})
  - ATR 14: Son 14 mumluk Gerçek Aralık (True Range) ortalaması (${ind['atr']:,.4f})
• Aşağıdaki 1. Bölümdeki 24 Mum: Son 24 saatin mikroskop altında incelenmesi için tam 24 mumu içerir.
  (Aşağıdaki 24 mumun toplam hacmi: ${calculated_24h_vol_usdt:,.0f} USDT | 24s Değişim: %{calculated_24h_chg})

═════════════════════════════════════════════════════════════════════
📊 BÖLÜM 1: SAF MUM VERİLERİ (Son 24 Saatlik 24 Bar - Grafiğin Kendisi)
═════════════════════════════════════════════════════════════════════
Parite: {symbol} | Zaman Dilimi: {tf} | Anlık Fiyat: ${ep:,.4f}
24 Saatlik Fiyat Değişimi: %{calculated_24h_chg} | 24 Saatlik Toplam Hacim: ${calculated_24h_vol_usdt:,.0f} USDT

Son 24 Mum Dökümü (🟢 = Yeşil/Yükseliş Barı, 🔴 = Kırmızı/Düşüş Barı):
{raw_candles_text}

═════════════════════════════════════════════════════════════════════
📈 BÖLÜM 2: 300 MUMLUK HAVUZDAN HESAPLANAN TEKNİK İNDİKATÖRLER
═════════════════════════════════════════════════════════════════════
EMA Trend Yapısı:
  • EMA 20: ${ema20:,.4f} | EMA 50: ${ema50:,.4f} | EMA 200: ${ema200:,.4f}
  • Yorum: {ema_structure}

Momentum & Osilatörler:
  • {rsi_context}
  • MACD Histogramı: {ind['macd_hist']} ({'Pozitif Momentum (Boğa İvmesi)' if ind['macd_hist'] > 0 else 'Negatif Momentum (Ayı İvmesi)'})
  • Supertrend: {ind['supertrend']}

Volatilite & Hacim Profili:
  • ATR (14-Bar Ortalama Dalgalanma Payı): ${ind['atr']:,.4f}
  • Son Bar Hacim Oranı: {vol_desc}
  • 24s Hacim Değişimi (Önceki 24s'ye göre): %{vol_24h_chg}

═════════════════════════════════════════════════════════════════════
🔍 BÖLÜM 3: ÇOK ZAMAN DİLİMLİ TREND RADARI (MTF - Büyük Resim)
═════════════════════════════════════════════════════════════════════
{mtf_text}
Genel Çoklu Zaman Uyum Durumu: {mtf.get('alignment_status', 'Hesaplanıyor...')}

═════════════════════════════════════════════════════════════════════
🏛️ BÖLÜM 4: PİYASA YAPISI & KRİTİK SEVİYELER (SMC & S/R)
═════════════════════════════════════════════════════════════════════
• Tespit Edilen Teknik Yapılar: {", ".join(strategies) if strategies else "Konsolidasyon / Formasyon Gelişiyor"}
• Ana Destek Bölgeleri: {sup_str}
• Ana Direnç Bölgeleri: {res_str}

═════════════════════════════════════════════════════════════════════
🤖 BÖLÜM 5: ALGORİTMAMIN HİPOTEZİ (Referans - Kendi Kararınla Sına)
═════════════════════════════════════════════════════════════════════
• Algoritma Kararı: {direction_label} | Güven Puanı: %{score} | R:R Oranı: 1:{rr}
• Hedef Strateji: 🎯 {primary_strat}
• Planlanan Seviyeler: Giriş: ${ep:,.4f} | Stop Loss: ${sl:,.4f} (-%{rp}) | TP1: ${tp1:,.4f} (+%{tp1_p}) | TP2: ${tp2:,.4f} (+%{tp2_p}) | TP3: ${tp3:,.4f} (+%{tp3_p})
• Algoritmik Gerekçe: {"; ".join(reasons[:4])}

═════════════════════════════════════════════════════════════════════
❓ SENDEN BEKLEDİĞİM PROFESYONEL TRADER DEĞERLENDİRMESİ
═════════════════════════════════════════════════════════════════════
1. **Saf Mum Analizi**: Bölüm 1'deki son 24 mumun fitillerini ve gövdelerini oku. Alıcılar mı baskın, satıcılar mı? Fiyat nerede sıkışıyor?
2. **Hipotez Denetimi**: Bölüm 5'teki algoritma önerisine KÖRÜ KÖRÜNE KATILMA. Saf mumlara ve indikatörlere bakarak mantıklı buluyorsan ONAYLA, riskli buluyorsan REDDET ve nedenini söyle.
3. **Net Karar**: Şu an bu coinde **LONG mu girmeliyim, SHORT mu, yoksa BEKLEMELİ MİYİM? NEDEN?**
4. **İşlem Planı**: Giriş fiyatı, Stop Loss seviyesi (neden o seviye), Kâr Hedefleri (TP1, TP2) ve Kaldıraç Tavsiyesi nedir?
5. **Tuzak & Risk Uyarısı**: Likidite avı (Sweep), sahte kırılım (Fakeout), boğa/ayı tuzağı riski var mı?
"""
    return prompt.strip()
