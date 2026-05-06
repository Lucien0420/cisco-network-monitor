# Cisco Switch Real-time Monitor Engine

[![CI](https://github.com/Lucien0420/cisco-network-monitor/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Lucien0420/cisco-network-monitor/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**語言：** [English](README.md) · [繁體中文](README.zh-TW.md)

針對 Cisco 網路設備（Catalyst 9000 / IOS-XE）設計的高效能監控引擎。採用 **ETL (Extract-Transform-Load)** 架構，透過 **Netmiko** 進行多設備並發採集，利用 **FastAPI** 提供結構化數據介面，並以 **Streamlit** 呈現互動式 NOC 儀表板。

![儀表板截圖](images/dashboard.png)

**Demo 影片（YouTube）：**[觀看完整展示](https://youtu.be/cuApdgCYuGg) — 包含多設備並發採集、即時指標圖表與 HTTPS 設定。

---

## 核心設計：ETL 資料流水線

本專案的核心是一個完整的資料處理流水線，確保從原始 CLI 輸出到視覺化圖表的每一階段都具備高度的可擴展性：

1.  **Extract (抽取)**：`monitor.py` 透過 `driver.py` (Netmiko) 經由 SSH 連接設備，執行 `show` 指令獲取非結構化文字。
2.  **Transform (轉換)**：`data_cleaning.py` 利用正則表達式 (Regex) 解析器將文字轉換為結構化 JSON 數據。
3.  **Load (載入)**：`database.py` 將結構化數據與原始指標存入 **SQLite** 時序資料庫。

---

## 核心功能

- **多設備並發監控**：利用 `ThreadPoolExecutor` 實現非阻塞式採集，支援同時監控數十台交換機。
- **動態指標解析**：內建 `cpu`、`memory`、`version`、`vlan`、`interfaces` 等解析器，支援 `/reload-parsers` 熱重載。
- **專業級模擬器**：內建 `sim/switch_simulator.py`，支援多執行緒 SSH 連線、動態 CPU 波動與記憶體洩漏模擬，實現 100% 離線開發與 CI 測試。
- **互動式 NOC 儀表板**：
    - **設備過濾**：側邊欄支援多選過濾，快速切換觀測目標。
    - **時序分析**：Altair 互動式圖表，支援縮放、平移與多指標切換。
    - **硬體清單**：即時呈現 `show inventory` 與介面狀態詳情。
- **企業級安全**：FastAPI + OAuth2 (JWT) 身份驗證，支援 Nginx 反向代理與 HTTPS (mkcert)。

---

## 技術棧

| 層級 | 技術 |
|------|------|
| **語言** | Python 3.10+ |
| **連線驅動** | Netmiko 4.3.0 (基於 Paramiko) |
| **並發模型** | Multi-threading (ThreadPoolExecutor) |
| **資料儲存** | SQLite |
| **後端框架** | FastAPI, Uvicorn |
| **前端框架** | Streamlit, Altair, Pandas |
| **測試框架** | Pytest |
| **部署工具** | Docker (選配), Nginx, mkcert |

---

## 專業交換機模擬器 (Supporting Role)

這不是簡單的數據 Mock，而是一個基於 **Paramiko** 實現的完整 **SSH 伺服器**，具備極高的技術含金量：

- **真實通訊協定**：支援真實的 SSH 握手、身份驗證與互動式 Shell 模擬，監控引擎完全感知不到其為模擬設備。
- **獨立個性化 (Personality)**：每台連線的虛擬設備擁有獨立的基底數值與波動時間軸。
- **動態趨勢模擬**：
    - **CPU**：正弦波波動 + 隨機突發尖峰。
    - **Memory**：模擬持續性記憶體洩漏。
    - **Interface**：特定埠口隨機 Up/Down 狀態切換。
- **高併發測試**：單一模擬器實例即可同時處理多個 SSH 連線，完美模擬大規模網路環境。
- **開發優勢**：實現 100% 離線開發與 CI 自動化測試，無需依賴不穩定的真實沙盒環境。

---

## 快速開始

### 1. 本地開發環境

```bash
git clone <repository-url>
cd switch
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 2. 啟動模擬器與監控

#### 選項 A：手動啟動 (本地)

```bash
# 啟動 5 台模擬交換機 (背景執行)
for port in {2222..2226}; do
  python3 sim/switch_simulator.py --port $port &
done

# 啟動監控、API 與儀表板
bash scripts/restart_all.sh
```

#### 選項 B：使用 Docker Compose (推薦)

```bash
# 1. 準備 Docker 專用設定
cp devices.docker.json.example devices.json

# 2. 一鍵啟動所有服務 (含 5 台模擬器)
docker-compose up -d
```

開啟 **http://localhost:8501** 即可進入儀表板。

---

## 測試與 CI

本專案使用 **Pytest** 進行自動化測試，確保解析邏輯的準確性：

```bash
# 執行單元測試
python3 -m pytest tests/
```

在 GitHub Actions 中，每次 Push 都會自動執行測試，驗證 ETL 轉換邏輯與 API 健康狀態。

---

## 專案結構

```text
.
├── main.py                  # 引擎入口：排程並發採集任務
├── api.py                   # REST API：提供 JWT 驗證與結構化數據
├── streamlit_app.py         # Dashboard：互動式視覺化介面
├── data_cleaning.py         # ETL Transform：Regex 解析核心
├── driver.py                # Netmiko 封裝：SSH 通訊層
├── sim/
│   └── switch_simulator.py  # 專業模擬器：支援動態指標與多執行緒
├── tests/                   # 自動化測試套件
├── data/                    # SQLite 資料庫 (gitignored)
└── docs/                    # 詳細技術文件與 HTTPS 設定
```

---

## 授權

MIT License — 詳見 [LICENSE](LICENSE) 檔案。
