# 🚀 Quick Start Guide - Multi-Account Copy Trading Bot

## Step 1: Install Dependencies & Setup

If you are on Windows, simply double-click **`setup.bat`**. This will automatically create the virtual environment, install dependencies, and create the `.env` template.

*(Alternatively, or if on Mac/Linux)*
```bash
# Windows
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Step 2: Configure Your Wallet

1. Copy `.env.example` to `.env` (already done if you used `setup.bat`!):
```bash
# Windows
copy .env.example .env

# Mac/Linux
cp .env.example .env
```

2. Edit `.env` and add your wallet details and GitHub Token:
```env
FUNDER_ADDRESS=0xYourWalletAddress
PRIVATE_KEY=your_private_key
GITHUB_TOKEN=ghp_YourGitHubTokenHere
```
*(You can generate a classic Personal Access Token on GitHub under Settings -> Developer Settings -> PATs. Give it `repo` scope).*

## Step 3: Start the Web Server

```bash
python web_gui.py
```

## Step 4: Open the GUI

Open your browser and go to:
```
http://localhost:5000
```

## Step 5: Add Target Accounts

1. In the "Tracked Accounts" section, click **"+ Add Account"**
2. Enter the wallet address you want to copy (starts with 0x...)
3. Give it a friendly name (e.g., "Top Trader")
4. Optionally set a custom bet amount for this account
5. Click **"Add Account"**

Repeat for each trader you want to track.

## Step 6: Start the Bot

1. Make sure **"Dry Run Mode"** is ON (toggle should be green)
2. Click **"▶ Start Bot"**
3. Watch it simulate trades for a while
4. When ready for live trading, toggle **"Dry Run Mode"** OFF

## Step 7: Monitor Your Portfolio

- View real-time P&L in the stats cards
- See all open positions
- Export data to Excel anytime
- Record withdrawals for tracking

## 🎯 That's It!

The bot will now:
- Check all your tracked accounts every 60 seconds
- Wait 2 seconds between each account (rate limiting)
- Copy new trades automatically
- Track everything in the database
- Show real-time stats in the GUI

## 💡 Pro Tips

1. **Start with 1-2 accounts** to test
2. **Always use dry run first** 
3. **Set custom bet amounts** for each account based on their track record
4. **Export data regularly** for analysis
5. **Disable accounts** instead of removing them (keeps history)

## ⚠️ Important

- Never share your private key
- Always test in dry run mode first
- Monitor your positions daily
- Set bet amounts you're comfortable with
- The bot runs 24/7 when started - stop it when not needed

## 📊 Excel Export

Click any of these buttons anytime:
- **📊 Export Positions** - Current positions
- **📜 Export History** - All trade history  
- **📑 Full Report** - Everything in one file

## 🆘 Need Help?

See the full README (MULTI_ACCOUNT_README.md) for detailed documentation.

---

**Enjoy automated copy trading! 🚀**
