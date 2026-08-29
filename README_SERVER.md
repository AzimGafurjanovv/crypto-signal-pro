# ⚡ CryptoSignalPro AI - 2 Dakikada Kolay Sunucu Kurulum Kılavuzu

Bu proje, bir Linux sunucuda (Hetzner, DigitalOcean, Contabo, AWS vb.) **7/24 kesintisiz çalışacak ve tek tuşla güncellenecek** şekilde optimize edilmiştir.

---

## 🚀 1. Adım: Projeyi Sunucuya İndirin (Tek Satır)

Sunucunuza SSH ile bağlanın ve şu komutu yapıştırın:

```bash
git clone https://github.com/KULLANICI_ADINIZ/crypto-signal-pro.git
cd crypto-signal-pro
```

---

## ⚡ 2. Adım: Otomatik Kurulumu Başlatın (Tek Satır)

```bash
chmod +x deploy.sh update.sh
./deploy.sh
```

Bu script her şeyi otomatik yapar:
- Python, Nginx ve güvenlik duvarını kurar.
- `cryptosignal.service` servisiyle projeyi **7/24 arka plana** alır.
- `http://SUNUCU_IP_ADRESINIZ` üzerinden sitenizi canlıya açar.

---

## 🔄 3. Adım: Sık ve Kolay Güncelleme (Tek Satır)

Yeni bir kod yazdığınızda sunucuyu güncellemek için sadece:

```bash
./update.sh
```

veya GitHub Webhook / Actions ile siz `git push` yaptığınız anda sunucu **kendi kendini otomatik olarak günceller**!
