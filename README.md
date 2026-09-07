# 🤖 Polymarket Copy Trader — Multi-Account Automated Execution Engine & Web Dashboard

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python)](https://python.org)
[![Web Interface](https://img.shields.io/badge/Web%20GUI-Flask%20%2F%20HTML5-red.svg)](https://flask.palletsprojects.com/)
[![Market Platform](https://img.shields.io/badge/Platform-Polymarket%20CLOB-purple.svg)](https://polymarket.com)
[![Network](https://img.shields.io/badge/Network-Polygon%20PoS-8247E5.svg?logo=polygon)](https://polygon.technology)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Polymarket Copy Trader** is an enterprise-grade automated trading system that mirrors high-performing wallets across decentralized prediction markets (**Polymarket**). 

The platform features an autonomous multi-threaded execution engine, a comprehensive **Flask-based Web GUI** for real-time portfolio telemetry, and an integrated **Node.js leaderboard scraper** that discovers and analyzes top-ranking profitable traders on-chain.

---

## 🏛️ System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                      PROFITABLE WALLET DISCOVERY                       │
│  Node.js Scraper continuously audits on-chain Polymarket leaderboards,  │
│  filtering for sustained win rates, volume thresholds, and ROI.        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Target Wallet Addresses
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     MONITORING & SYNCHRONIZATION                       │
│  • Continuous async polling loop checking on-chain activity            │
│  • Microsecond detection of new fills, bets, and position changes      │
│  • Anti-frontrunning & rate-limiting queue (2s interval per account)   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Normalized Trade Signals
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   ORDER ROUTING & RISK MANAGEMENT                      │
│  • Dynamic bet sizing per target wallet ($2, $5, $10, etc.)            │
│  • Dry-Run Paper Trading Mode (Zero-risk simulation)                   │
│  • EIP-712 cryptographic order generation via Polymarket CLOB          │
│  • SQLite persistence: trade history, open positions, P&L metrics      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Telemetry & State
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      FLASK REAL-TIME WEB GUI                           │
│  • Live Dashboard: Open positions, PnL curve, active bot status        │
│  • Account Management: Add, pause, or customize tracked wallets        │
│  • Comprehensive Reporting: One-click Excel export for accounting      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Key Capabilities

- **Interactive Web Management Interface**: Control the entire bot via a sleek browser dashboard at `http://localhost:5000`—start/stop the engine, toggle between live and paper trading, add new targets, and inspect positions.
- **Risk-Free Simulation (Dry Run Mode)**: Test copying strategies with zero financial exposure. The system records simulated executions, computes realistic fills, and tracks theoretical P&L.
- **Granular Account Customization**: Set individualized position sizes and maximum trade frequencies per tracked wallet based on historical volatility.
- **Leaderboard Scraper Suite**: Includes `polymarket-profitablewallets-scrapper` to discover whales, calculate profitability metrics, and rank wallets before adding them to your portfolio.
- **Full Excel & Financial Reporting**: Instantly export structured reports covering open positions, historical closed trades, and cumulative performance metrics.

---

## 🛠️ Quickstart & Installation

### 1. Prerequisites
- **Python 3.10+**
- **Node.js 18+** (for the wallet discovery scraper)
- **Polygon Wallet**: Funded with USDC.e on Polygon PoS

### 2. Repository Setup
```bash
git clone https://github.com/kawacoline/Polymarket-Copy-Kawa.git
cd Polymarket-Copy-Kawa
setup.bat
```

*(On Linux / macOS)*:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Credentials
Copy `.env.example` to `.env`:
```bash
copy .env.example .env
```

Set your execution wallet:
```ini
FUNDER_ADDRESS=0xYourPolygonWalletAddress
PRIVATE_KEY=0xYourPrivateKey

# Optional initial defaults
SIGNATURE_TYPE=1
BET_AMOUNT=2.0
DRY_RUN=True
```

### 4. Start the Web Control Center
Launch the web interface:
```bash
python web_gui.py
```
Open your browser at **`http://localhost:5000`**.

---

## 📊 Operating Guide

1. **Add Target Accounts**: From the web dashboard, click **`+ Add Account`**, enter the target trader's wallet address, assign an alias, and specify your desired bet multiplier.
2. **Engage Dry-Run Mode**: Keep the green **`Dry Run Mode`** toggle enabled to verify execution on incoming trades.
3. **Activate Bot**: Click **`▶ Start Bot`**. The worker process will continuously synchronize trades in the background.
4. **Export Analytics**: Use **`📊 Export Positions`** or **`📑 Full Report`** anytime to generate complete `.xlsx` audit spreadsheets.

---

## 📁 Project Structure

```
├── web_gui.py                  # Flask web dashboard application
├── continuous_bot.py           # Core asynchronous copy-trading worker
├── launcher.py                 # Supervisor and process manager
├── betting_logger.py           # SQLite database layer and trade recorder
├── requirements.txt            # Python dependencies
├── static/ & templates/        # Modern front-end assets (HTML, CSS, JS)
├── polymarket-profitablewallets-scrapper/ # Node.js whale & leaderboard analyzer
│   ├── src/index.js            # Scraper entrypoint
│   └── src/leaderboard.js      # On-chain profitability ranker
├── setup.bat / start.bat       # Automated Windows orchestration scripts
└── .env.example                # Sanitized configuration template
```

---

## 👨‍💻 Author

**Hazael**  
*Full Stack Software Engineer & Web3 Automation Specialist*  
- **GitHub**: [@kawacoline](https://github.com/kawacoline)  
- **Email**: kawacoline@gmail.com  
- **Portfolio**: [hazael.dev](https://github.com/kawacoline)

---

## ⚖️ Disclaimer

*This software is released strictly for research and portfolio demonstration. Copying trades from external wallets involves inherent risks including slippage, liquidity constraints, and counterparty performance. Always maintain strict risk controls.*
