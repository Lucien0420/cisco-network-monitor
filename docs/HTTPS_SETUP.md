# monitor.switch.test HTTPS Setup Guide

Use mkcert to generate locally-trusted SSL certificates for development, so the browser shows a padlock (🔒).

---

## Quick Start

```bash
# 1. Run setup script (installs mkcert, creates CA, generates certificates)
bash scripts/setup_https_mkcert.sh

# 2. Update nginx config
sudo cp certs/nginx_https_example.conf /etc/nginx/sites-available/switch_monitor
# Or manually edit /etc/nginx/sites-available/switch_monitor and add SSL block

# 3. Test and reload nginx
sudo nginx -t
sudo systemctl reload nginx
```

Visit **https://monitor.switch.test** — it should show the padlock.

---

## Step Details

### Step 1: Install mkcert

**Purpose**: mkcert creates locally-trusted development certificates.

- Public CAs (e.g. Let's Encrypt) issue certificates trusted by all browsers
- mkcert creates a **local CA** — only your machine's browser trusts it
- Suitable for development only, not production

**Command**:
```bash
sudo apt-get install -y libnss3-tools mkcert
```

---

### Step 2: Create local CA (mkcert -install)

**Purpose**: Register a local Certificate Authority on your system.

- mkcert generates a CA certificate and installs it in the system trust store
- Certificates signed by this CA will be trusted by the browser
- Run once per machine

**Command**:
```bash
mkcert -install
```

---

### Step 3: Generate certificate for monitor.switch.test

**Purpose**: Generate SSL certificate and private key for your domain.

- `monitor.switch.test.pem` — certificate (can be shared)
- `monitor.switch.test-key.pem` — private key (**never expose**)

**Command**:
```bash
cd certs
mkcert monitor.switch.test
```

---

### Step 4: Configure nginx

**Purpose**: Make nginx listen on port 443 and use the certificates.

Key settings (replace `PROJECT_ROOT` with your project path):
```nginx
listen 443 ssl;
ssl_certificate     PROJECT_ROOT/certs/monitor.switch.test.pem;
ssl_certificate_key PROJECT_ROOT/certs/monitor.switch.test-key.pem;
```

**HTTP to HTTPS redirect** (optional):
```nginx
server {
    listen 80;
    server_name monitor.switch.test;
    return 301 https://$server_name$request_uri;
}
```

---

## Notes

1. **Local only**: Other machines will not trust this certificate unless they run `mkcert -install` with your CA
2. **Private key**: Do not commit `*-key.pem` to Git; it is in `.gitignore`
3. **API URL**: If the Streamlit dashboard uses `http://monitor.switch.test:8000`, you can switch to `https://` if the API also has HTTPS, or keep `http://` (API usually does not need HTTPS for internal requests)

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Browser shows "Connection not private" | **WSL2 users**: Browser runs on Windows; install mkcert on Windows and run `mkcert -install`. See **docs/HTTPS_WSL2_WINDOWS.md** |
| nginx fails to start | Run `sudo nginx -t` to check config; verify certificate paths |
| 502 Bad Gateway | Is Streamlit running on port 8501? `curl http://127.0.0.1:8501` |
