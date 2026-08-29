#!/bin/bash
# ==============================================================================
# CryptoSignalPro AI - Linux Sunucu Otomatik İlk Kurulum Scripti (deploy.sh)
# Desteklenen Sistemler: Ubuntu 20.04 / 22.04 / 24.04 & Debian 11 / 12
# ==============================================================================

set -e

echo "📦 [1/6] Sistem paketleri güncelleniyor ve gerekli araçlar kuruluyor..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git nginx ufw curl

PROJECT_DIR=$(pwd)
USER_NAME=$(whoami)

echo "🐍 [2/6] Python sanal ortamı (venv) oluşturuluyor..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "⚙️ [3/6] Systemd 7/24 Arka Plan Servisi Oluşturuluyor..."
SERVICE_FILE="/etc/systemd/system/cryptosignal.service"

sudo bash -c "cat > $SERVICE_FILE" <<EOL
[Unit]
Description=CryptoSignalPro AI Production Server
After=network.target

[Service]
User=$USER_NAME
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python run.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOL

echo "🔄 [4/6] Servis başlatılıyor ve başlangıca ekleniyor..."
sudo systemctl daemon-reload
sudo systemctl enable cryptosignal
sudo systemctl restart cryptosignal

echo "🌐 [5/6] Nginx Reverse Proxy Yapılandırılıyor..."
NGINX_CONF="/etc/nginx/sites-available/cryptosignal"
sudo bash -c "cat > $NGINX_CONF" <<EOL
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
    }
}
EOL

sudo ln -sf /etc/nginx/sites-available/cryptosignal /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

echo "🛡️ [6/6] Güvenlik duvarı (UFW) ayarlanıyor..."
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable || true

echo ""
echo "=========================================================================="
echo "🎉 TEBRİKLER! CryptoSignalPro AI Sunucuda 7/24 Canlıya Alındı!"
echo "🌐 Sunucu IP adresiniz üzerinden tarayıcınızdan erişebilirsiniz!"
echo "🔄 Güncellemeler için: ./update.sh çalıştırmanız yeterlidir!"
echo "=========================================================================="
