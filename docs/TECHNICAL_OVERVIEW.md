# Cisco Network Monitoring System
## Technical Overview

---

## 📊 System Overview

A production-ready network monitoring solution for Cisco devices (Catalyst 9000 and compatible). Automates SSH-based data collection, stores metrics in SQLite, and provides a real-time web dashboard with secure HTTPS access.

**Tested on**: Cisco DevNet Sandbox (Catalyst 9000) with 500+ data points collected.

---

## ✨ Key Features

### Monitoring Capabilities
- **6 core metrics**: CPU usage, memory usage, system uptime, VLAN count, interface status, interface summary
- **Real-time data collection**: Configurable polling intervals (default: 30 seconds)
- **Multi-device support**: Concurrent monitoring via ThreadPoolExecutor
- **Flexible configuration**: JSON-based device definitions

### Data Management
- **SQLite database**: Time-series storage with device isolation
- **Data parsing**: Extensible parsers for Cisco CLI output (Catalyst 9000 format)
- **REST API**: FastAPI backend with JWT authentication
- **Data export**: API endpoints for raw/cleaned/time-series data

### Visualization
- **Interactive dashboard**: Streamlit-based web UI
- **Time-series charts**: Altair charts with zoom/pan controls
- **Detailed tables**: Interface status and VLAN configuration
- **Metric selector**: Toggle between metrics with state retention

### Professional Deployment
- **Nginx reverse proxy**: Custom domain with reverse proxy configuration
- **HTTPS support**: mkcert for trusted local certificates
- **Production-ready**: Background process management with restart scripts
- **Logging**: Structured logging with rotation

---

## 🛠️ Technology Stack

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| **Device Connection** | Netmiko | 4.3.0 | SSH client for Cisco devices |
| **Data Storage** | SQLite | 3.x | Time-series metrics database |
| **Backend API** | FastAPI | Latest | RESTful API with OAuth2/JWT |
| **Frontend UI** | Streamlit | Latest | Interactive dashboard |
| **Visualization** | Altair | Latest | Time-series charts |
| **Concurrency** | ThreadPoolExecutor | stdlib | Multi-device monitoring |
| **Web Server** | Nginx | Latest | Reverse proxy + HTTPS |
| **SSL/TLS** | mkcert | Latest | Trusted local certificates |

### Tested Platforms
- ✅ Cisco Catalyst 9000 series (9200, 9300, 9400)
- ✅ Cisco IOS / IOS-XE

### Other Vendors (Customization Available)
- ⚙️ Juniper JunOS (requires custom command mapping)
- ⚙️ Arista EOS (requires parser customization)
- ⚙️ HP/Aruba (requires command adaptation)
- ⚙️ IOS-XR / NX-OS (requires command customization)

---

## 🏗️ System Architecture

```
┌─────────────────┐
│  Cisco Switch   │  SSH connection via Netmiko
│  (Real Device)  │  Commands: show version, show cpu, etc.
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│   main.py       │────▶│   SQLite     │
│   monitor.py    │     │   Database   │
│   driver.py     │     └──────┬───────┘
│ (Collector)     │            │
└─────────────────┘            │
                               ▼
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Streamlit UI   │────▶│   api.py     │────▶│ data_cleaning.py│
│  (port 8501)    │     │ (port 8000)  │     │   (Parsers)     │
└────────┬────────┘     └──────────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐
│     Nginx       │  https://monitor.switch.test
│ Reverse Proxy   │  + mkcert SSL certificate
└─────────────────┘
```

---

## 📦 Deliverables

### Source Code
- Complete Python codebase (8 core modules)
- Configuration files (`devices.json`, `requirements.txt`)
- Deployment scripts (`restart_all.sh`)

### Documentation
- `README.md` — Installation, configuration, API reference
- `docs/HTTPS_SETUP.md` — HTTPS setup for Linux
- `docs/HTTPS_WSL2_WINDOWS.md` — HTTPS setup for WSL2
- This technical overview

### Sample Data
- Sample monitoring data (CSV format)
- Demonstrates data structure and parsing results

### Deployment Configuration
- Nginx configuration template
- SSL certificate setup scripts
- Service management examples

---

## 🎯 Use Cases

### Network Operations
- Monitor switch health (CPU, memory, uptime)
- Track interface status changes
- Audit VLAN configurations
- Detect performance anomalies

### Automation & Reporting
- Automated data collection and storage
- Historical trend analysis
- Export data for external reporting tools
- Integration with existing monitoring systems

### Development & Testing
- Test environment for network automation scripts
- API for third-party integrations
- Template for custom monitoring solutions

---

## 🔧 Customization Options

### Add New Metrics
1. Define command in `devices.json`
2. Add parser in `data_cleaning.py`
3. Metric automatically appears in dashboard

### Multi-Device Scaling
- Supports unlimited devices (limited by system resources)
- Each device runs in separate thread
- Device isolation in database

### Integration
- REST API for external tools
- JWT authentication for secure access
- CSV/JSON export via API endpoints

---

## 📈 Performance

- **Data collection**: ~10-15 seconds per device per cycle (6 commands)
- **Database**: Handles 10,000+ records with instant queries
- **Dashboard**: Real-time updates without manual refresh
- **API response**: <100ms for time-series queries

---

## 🔒 Security

- **Authentication**: JWT-based (OAuth2 password flow)
- **HTTPS**: mkcert trusted certificates (no browser warnings)
- **Credentials**: Environment variables (not hardcoded)
- **API keys**: Masked in API responses

---

## 🚀 Production Deployment

### System Requirements
- Linux/WSL2 (Ubuntu 20.04+)
- Python 3.10+
- Nginx (reverse proxy)
- SSH access to target devices

### Resource Usage
- **CPU**: <5% idle, <15% during collection
- **Memory**: ~100MB per device
- **Disk**: ~1MB per 1000 records
- **Network**: Minimal (SSH only)

---

## 📞 Support & Customization

### Customization Options
✅ Add custom metrics (additional commands)  
✅ Extend to other device types (Juniper, Arista, HP)  
✅ Custom alerting (email/Slack/webhook integration)  
✅ Cloud deployment (AWS/GCP/Azure)  
✅ Integration with existing monitoring systems  
✅ Multi-vendor environment support  

### Technical Support
- Installation and configuration guidance
- Documentation and usage examples
- Troubleshooting assistance
- Code review and optimization suggestions

---

**Version**: 1.0  
**Last Updated**: March 2026  
**License**: MIT
