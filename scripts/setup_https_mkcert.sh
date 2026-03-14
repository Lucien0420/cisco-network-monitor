#!/bin/bash
# mkcert HTTPS setup script
# Generates locally-trusted SSL certificates for monitor.switch.test
# Run: bash scripts/setup_https_mkcert.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CERTS_DIR="${PROJECT_ROOT}/certs"

echo "=============================================="
echo "  mkcert HTTPS Setup - monitor.switch.test"
echo "=============================================="
echo ""

# ---------------------------------------------------------------------------
# Step 1: Install mkcert
# mkcert creates locally-trusted dev certificates (browser shows padlock)
# ---------------------------------------------------------------------------
echo "[Step 1] Checking if mkcert is installed..."
if ! command -v mkcert &>/dev/null; then
    echo "  mkcert not found, installing..."
    echo "  -> Installing libnss3-tools (mkcert dependency) and mkcert"
    sudo apt-get update -qq
    sudo apt-get install -y libnss3-tools
    sudo apt-get install -y mkcert
    echo "  Done: mkcert installed"
else
    echo "  mkcert already installed"
fi
echo ""

# ---------------------------------------------------------------------------
# Step 2: Create local CA (mkcert -install)
# Registers a local CA; certificates signed by it will be trusted by the browser
# ---------------------------------------------------------------------------
echo "[Step 2] Creating local CA (mkcert -install)..."
echo "  -> This creates a local Certificate Authority on your system"
echo "  -> Browsers will trust certificates signed by this CA (padlock icon)"
mkcert -install
echo "  Done: Local CA created"
echo ""

# ---------------------------------------------------------------------------
# Step 3: Generate certificate for monitor.switch.test
# Output: monitor.switch.test.pem (cert), monitor.switch.test-key.pem (private key)
# ---------------------------------------------------------------------------
echo "[Step 3] Generating certificate for monitor.switch.test..."
mkdir -p "$CERTS_DIR"
cd "$CERTS_DIR"

echo "  -> Writing to ${CERTS_DIR}/"
mkcert monitor.switch.test

echo "  Done: Certificates generated:"
ls -la *.pem 2>/dev/null || true
echo ""

# ---------------------------------------------------------------------------
# Step 4: Show nginx setup instructions
# ---------------------------------------------------------------------------
echo "[Step 4] Next: update nginx configuration manually"
echo ""
echo "  Certificate paths:"
echo "    Cert: ${CERTS_DIR}/monitor.switch.test.pem"
echo "    Key:  ${CERTS_DIR}/monitor.switch.test-key.pem"
echo ""
echo "  Edit /etc/nginx/sites-available/switch_monitor"
echo "  Reference: docs/HTTPS_SETUP.md or certs/nginx_https_example.conf"
echo ""
echo "  After editing, run:"
echo "    sudo nginx -t          # Test config"
echo "    sudo systemctl reload nginx"
echo ""
echo "=============================================="
echo "  mkcert setup complete!"
echo "=============================================="
