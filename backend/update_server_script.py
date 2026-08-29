import paramiko

def update_server_auto_sync():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect('47.251.110.202', 22, 'root', 'AzimAzim1')
    
    script = """cat > /root/crypto-signal-pro/auto_sync.sh << 'EOL'
#!/bin/bash
cd /root/crypto-signal-pro || exit

git fetch origin main > /dev/null 2>&1
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" != "$REMOTE" ]; then
    echo "[$(date)] Yeni güncelleme tespit edildi! Otomatik çekiliyor..." >> /var/log/crypto_autosync.log
    git reset --hard origin/main >> /var/log/crypto_autosync.log 2>&1
    source venv/bin/activate
    pip install -r requirements.txt >> /var/log/crypto_autosync.log 2>&1
    systemctl restart cryptosignal
    echo "[$(date)] Sistem başarıyla güncellendi ve yeniden başlatıldı." >> /var/log/crypto_autosync.log
fi
EOL
chmod +x /root/crypto-signal-pro/auto_sync.sh
"""
    stdin, stdout, stderr = c.exec_command(script)
    c.exec_command("systemctl restart cryptosignal")
    print("auto_sync.sh updated and service restarted successfully!")
    c.close()

if __name__ == "__main__":
    update_server_auto_sync()
