"""
Setup 100% Automatic Auto-Sync on remote VPS (47.251.110.202)
"""
import paramiko
import sys

HOST = "47.251.110.202"
USER = "root"
PASSWORD = "AzimAzim1"

def run_ssh(client, cmd):
    print(f"\n🖥️ [REMOTE] {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd)
    while True:
        line = stdout.readline()
        if not line:
            break
        print(line, end="")
        sys.stdout.flush()
    return stdout.channel.recv_exit_status()

def main():
    print(f"🚀 Connecting to {USER}@{HOST}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, port=22, username=USER, password=PASSWORD, timeout=30)
    print("✅ SSH Connected!")

    # 1. Create auto_sync.sh
    script_content = """cat > /root/crypto-signal-pro/auto_sync.sh << 'EOL'
#!/bin/bash
cd /root/crypto-signal-pro || exit

# GitHub'daki son durumu sessizce kontrol et
git fetch origin main > /dev/null 2>&1

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" != "$REMOTE" ]; then
    echo "[$(date)] Yeni güncelleme tespit edildi! Otomatik çekiliyor..." >> /var/log/crypto_autosync.log
    git pull origin main >> /var/log/crypto_autosync.log 2>&1
    source venv/bin/activate
    pip install -r requirements.txt >> /var/log/crypto_autosync.log 2>&1
    systemctl restart cryptosignal
    echo "[$(date)] Sistem başarıyla güncellendi ve yeniden başlatıldı." >> /var/log/crypto_autosync.log
fi
EOL"""
    run_ssh(client, script_content)
    run_ssh(client, "chmod +x /root/crypto-signal-pro/auto_sync.sh")

    # 2. Add cron job to run auto_sync.sh every 2 minutes
    cron_cmd = '(crontab -l 2>/dev/null | grep -v "auto_sync.sh" ; echo "*/2 * * * * /root/crypto-signal-pro/auto_sync.sh") | crontab -'
    run_ssh(client, cron_cmd)
    run_ssh(client, "crontab -l")

    # 3. Test execute auto_sync.sh once
    run_ssh(client, "/root/crypto-signal-pro/auto_sync.sh")

    client.close()
    print("\n🎉 100% AUTOMATIC BACKGROUND SYNC INSTALLED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
