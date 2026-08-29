#!/bin/bash
# ==============================================================================
# CryptoSignalPro AI - Tek Komutla Otomatik Güncelleme Scripti (update.sh)
# ==============================================================================

echo "🚀 [1/4] Git'ten en son güncellemeler çekiliyor..."
git pull origin main

echo "📦 [2/4] Python kütüphaneleri güncelleniyor..."
source venv/bin/activate
pip install --upgrade -r requirements.txt

echo "🔄 [3/4] CryptoSignalPro AI servisi yeniden başlatılıyor..."
sudo systemctl restart cryptosignal

echo "✅ [4/4] Servis durumu kontrol ediliyor..."
sudo systemctl status cryptosignal --no-pager

echo ""
echo "🎉 TEBRİKLER! Güncelleme başarıyla tamamlandı ve sistem canlıya alındı!"
