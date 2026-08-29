"""
CryptoSignalPro AI - Kripto Sinyal & Setup Bulucu Web Uygulaması Başlatıcı
"""
import os
import sys
import webbrowser
import time
import uvicorn

def main():
    print("=" * 65)
    print("🚀 CryptoSignalPro AI - Kripto Sinyal & Setup Bulucu v2.0")
    print("=" * 65)
    print("✅ Çoklu Strateji: SMC (FVG/OB), RSI Uyumsuzluk, EMA Trend, Hacim")
    print("✅ Matematiksel Risk/Ödül (R:R), Dinamik TP1/TP2/TP3 & Stop Loss")
    print("✅ AI Analiz İçin Tek Tıkla Kapsamlı Prompt Kopyalama")
    print("✅ TradingView İnteraktif Mum Grafiği ve Seviye Çizimleri")
    print("=" * 65)
    
    backend_dir = os.path.join(os.path.dirname(__file__), "backend")
    sys.path.insert(0, backend_dir)
    
    port = 8000
    url = f"http://127.0.0.1:{port}"
    print(f"\n🌐 Web Arayüzü Başlatılıyor: {url}")
    print(f"💡 Tarayıcınız otomatik olarak açılacaktır. Durdurmak için Ctrl+C tuşlayın.\n")
    
    # Tarayıcıyı 1.5 saniye sonra otomatik aç
    def open_browser():
        time.sleep(1.5)
        webbrowser.open(url)
        
    import threading
    threading.Thread(target=open_browser, daemon=True).start()
    
    # FastAPI Sunucusunu Çalıştır
    uvicorn.run("app:app", host="0.0.0.0", port=port, app_dir=backend_dir, reload=False)

if __name__ == "__main__":
    main()
