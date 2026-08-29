# ⚡ CryptoSignalPro AI - Gelişmiş Kripto Sinyal ve Setup Bulucu

Piyasadaki en başarılı kurumsal alım-satım konseptleri (**Smart Money Concepts - SMC**, **Fair Value Gap - FVG**, **Order Block - OB**), **RSI Fiyat Uyumsuzlukları (Divergence)**, **EMA Trend Takibi** ve **Hacimli Kırılımlar** üzerine inşa edilmiş; **otomatik R:R, kademeli TP/SL hesaplayan**, **TradingView interaktif grafiklerine sahip** ve **AI için tek tıkla analiz promptu üreten** profesyonel kripto tarayıcı web uygulaması.

---

## ✨ Temel Özellikler

### 1. 🎯 Çoklu Strateji & Güven Skoru Motoru (Confluence Engine)
- **SMC Likidite & FVG (Dengesizlikler)**: Grafikteki doldurulmamış (unmitigated) FVG boşluklarını ve kurumsal Order Block (OB) emir bloklarını tespit eder.
- **RSI Pozitif / Negatif Uyumsuzluklar**: Fiyat ile RSI arasındaki Regular (Dönüş) ve Hidden (Trend Devamı) uyumsuzlukları yakalar.
- **EMA Trend & Pullback**: EMA 20, 50, 200 hizalanması ve dinamik ortalamalara yapılan geri çekilme testleri.
- **Hacim Analizi**: 20 periyotluk ortalamaya göre %50+ kurumsal hacim artışlarını filtreler.
- **Güven Skoru (%0 - %100)**: Her bir teyit faktörünün gücüne göre her setup'a matematiksel bir güven puanı atar.

### 2. ⚖️ Dinamik Risk / Kazanç (R:R) ve Kademeli TP/SL
- **Giriş Fiyatı (Entry)**: Güncel piyasa seviyesi.
- **Stop Loss (Zarar Kes - SL)**: ATR tabanlı ve Swing Low/High (yapısal dip/tepe) korumalı seviye.
- **Kademeli Hedefler**:
  - **TP1**: $1.5 \times R$ (İlk Kâr Alma / Riski Sıfırlama)
  - **TP2**: $2.5 \times R$ (Ana Hedef)
  - **TP3**: $4.0 \times R$ (Maksimum Trend Takibi)
- **Geçersizlik & İptal Filtresi**: Fiyat önceden stop seviyesini kırmışsa veya hedefine varmışsa setup'ı otomatik eler.

### 3. 📋 "AI İçin Kopyala" (Copy for AI Prompt)
Her setup kartında bulunan buton; coin paritesi, zaman dilimi, RSI/ATR/EMA metrikleri, tam Giriş/SL/TP seviyeleri ve hazır değerlendirme talimatını tek tıkla kopyalar. Kopyalanan prompt doğrudan **ChatGPT**, **Claude**, **Gemini** veya **DeepSeek**'e yapıştırılarak 2. bir yapay zeka görüşü alınabilir.

### 4. 📈 İnteraktif TradingView Grafikleri
- Modern TradingView Lightweight Charts V4 entegrasyonu.
- Mum grafiği, hacim sütunları, Giriş (Mavi), Stop Loss (Kırmızı), TP1-TP2-TP3 (Yeşil) seviyeleri anlık olarak çizilir.

---

## 🚀 Hızlı Başlangıç

Uygulamayı başlatmak için terminalde projenin bulunduğu klasöre gidin ve aşağıdaki komutu çalıştırın:

```bash
python run.py
```

Tarayıcınız otomatik olarak `http://127.0.0.1:8000` adresinde açılacaktır.

---

## 🛠️ Klasör Yapısı

```
crypto-signal-pro/
├── backend/
│   ├── app.py                      # FastAPI Web Sunucusu ve REST API Rotaları
│   └── engine/
│       ├── market_data.py          # Çoklu Gateway (Binance Vision, OKX, MEXC) Veri Çekici
│       ├── indicators.py           # EMA, RSI, ATR, Supertrend, MACD, Hacim motoru
│       ├── smc.py                  # FVG, Order Block, BOS/CHoCH, Likidite analizleri
│       ├── divergence.py           # RSI Pozitif ve Negatif Uyumsuzluk tarayıcısı
│       ├── setup_calculator.py     # R:R, TP1-3, SL, Güven Skoru & Gerekçe motoru
│       └── ai_prompt_generator.py  # LLM'ler için Zengin Markdown Prompt Üretici
├── frontend/
│   ├── index.html                  # Modern Glassmorphic Dark UI
│   ├── js/
│   │   ├── app.js                  # Tarama, Filtreleme, Kart Oluşturma ve UI Yönetimi
│   │   └── chart.js                # TradingView Lightweight Charts V4 Entegrasyonu
│   └── css/
│       └── style.css               # Özel Kripto Tema Animasyonları
├── run.py                          # Tek tıkla uygulamayı başlatan Python scripti
└── README.md
```

---

## ⚙️ Parametreler ve Filtreleme Seçenekleri

Web arayüzünde dilediğiniz gibi ayarlayabileceğiniz parametreler:
- **Zaman Dilimi**: 15m (Scalp), 1h (Önerilen), 4h (Swing), 1d (Ana Trend)
- **Gösterilecek Coin Sayısı ($N$)**: 5, 10, 20 veya 35 coin
- **İşlem Yönü**: Tümü, Sadece Long (🟢), Sadece Short (🔴)
- **Strateji Filtresi**: Tüm Stratejiler, SMC (FVG & Likidite), RSI Uyumsuzluk, EMA Trend, Hacimli Kırılım
- **Minimum Güven Skoru**: %45 - %90 arası kaydırıcı
