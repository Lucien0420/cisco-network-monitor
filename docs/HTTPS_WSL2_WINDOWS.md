# WSL2 + Windows Browser: mkcert Padlock

**Problem**: mkcert running in WSL installs the CA only in Linux. The browser runs on **Windows**, so Windows does not trust that CA.

**Solution**: **Generate certificates on Windows**, then copy them to WSL for nginx. Certificates signed by the Windows CA will be trusted by the browser.

---

## Step 1: Install mkcert on Windows and generate certificates

1. Download [mkcert-v1.4.4-windows-amd64.exe](https://github.com/FiloSottile/mkcert/releases), rename to `mkcert.exe`, place in `C:\Tools\`

2. Open **PowerShell as Administrator**:

```powershell
cd C:\Tools
.\mkcert.exe -install
.\mkcert.exe monitor.switch.test
```

This creates `monitor.switch.test.pem` and `monitor.switch.test-key.pem` in `C:\Tools\`.

---

## Step 2: Copy certificates to WSL

In **WSL terminal** (sudo required to overwrite files in certs):

```bash
# Replace PROJECT_ROOT with your project path (e.g. /home/wner/switch)
# Replace /mnt/c/Users/YOUR_USERNAME/Downloads with where you saved the .pem files
sudo cp /mnt/c/Users/YOUR_USERNAME/Downloads/monitor.switch.test.pem PROJECT_ROOT/certs/
sudo cp /mnt/c/Users/YOUR_USERNAME/Downloads/monitor.switch.test-key.pem PROJECT_ROOT/certs/
```

Verify issuer (should be Windows hostname, not wner@...):
```bash
openssl x509 -in PROJECT_ROOT/certs/monitor.switch.test.pem -noout -issuer
```

---

## Step 3: Reload nginx

```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## Step 4: Verify

Open **https://monitor.switch.test** in the Windows browser — it should show the padlock.

---

## Notes

- Certificates are generated on **Windows** and signed by the Windows CA, so the browser trusts them
- No need to touch mkcert or CA in WSL; avoids permission and sync issues
