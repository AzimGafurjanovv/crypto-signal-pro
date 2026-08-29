"""
CryptoSignalPro AI - Automated Remote VPS Deployment Script
Connects via SSH to 47.251.110.202 and deploys the entire application.
"""
import time
import sys
import paramiko

HOST = "47.251.110.202"
USER = "root"
PASSWORD = "AzimAzim1"

def run_ssh_command(client, cmd, timeout=300):
    print(f"\n🖥️ [REMOTE] Executing: {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    
    # Stream output live
    while True:
        line = stdout.readline()
        if not line:
            break
        print(line, end="")
        sys.stdout.flush()

    err = stderr.read().decode('utf-8', errors='ignore')
    if err and "warning" not in err.lower() and "debconf" not in err.lower():
        print(f"⚠️ STDERR: {err}")

    exit_status = stdout.channel.recv_exit_status()
    print(f"Status Code: {exit_status}")
    return exit_status

def deploy():
    print(f"🚀 Connecting to {USER}@{HOST}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(hostname=HOST, port=22, username=USER, password=PASSWORD, timeout=30)
        print("✅ SSH Connection Successful!")
    except Exception as e:
        print(f"❌ SSH Connection Failed: {e}")
        return

    commands = [
        # 1. Update packages & install dependencies
        "export DEBIAN_FRONTEND=noninteractive && apt-get update && apt-get install -y python3 python3-pip python3-venv git nginx ufw curl",
        
        # 2. Clone or pull repo
        "if [ -d '/root/crypto-signal-pro' ]; then cd /root/crypto-signal-pro && git pull origin main; else git clone https://github.com/AzimGafurjanovv/crypto-signal-pro.git /root/crypto-signal-pro; fi",
        
        # 3. Create venv & install requirements
        "cd /root/crypto-signal-pro && python3 -m venv venv && source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt",
        
        # 4. Create systemd service
        """cat > /etc/systemd/system/cryptosignal.service << 'EOL'
[Unit]
Description=CryptoSignalPro AI Production Server
After=network.target

[Service]
User=root
WorkingDirectory=/root/crypto-signal-pro
ExecStart=/root/crypto-signal-pro/venv/bin/python run.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOL""",
        
        # 5. Reload & Start systemd service
        "systemctl daemon-reload && systemctl enable cryptosignal && systemctl restart cryptosignal",
        
        # 6. Configure Nginx
        """cat > /etc/nginx/sites-available/cryptosignal << 'EOL'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
EOL""",
        
        # 7. Enable Nginx site & restart
        "rm -f /etc/nginx/sites-enabled/default && ln -sf /etc/nginx/sites-available/cryptosignal /etc/nginx/sites-enabled/ && nginx -t && systemctl restart nginx",
        
        # 8. Check health
        "sleep 3 && systemctl status cryptosignal --no-pager",
        "curl -I http://127.0.0.1:8000/"
    ]

    for cmd in commands:
        status = run_ssh_command(client, cmd)
        if status != 0 and "warning" not in cmd:
            print(f"⚠️ Non-zero exit code on command: {cmd}")

    client.close()
    print("\n🎉 ALL DEPLOYMENT COMMANDS COMPLETED!")

if __name__ == "__main__":
    deploy()
