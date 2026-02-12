# Mad Rabbit EA — QuickStart (Draft)

## 1) What You Need
- MetaTrader 5 (desktop)
- A demo account to test first
- Windows VPS if you want 24/7 uptime

## 2) Install the EA
1. Open MT5.
2. Go to **File → Open Data Folder**.
3. Open **MQL5 → Experts**.
4. Copy `Mad_Rabbit_Bot.ex5` into **Experts**.
5. Restart MT5 (or refresh the Navigator).

## 3) Enable Algo Trading
- Click **Algo Trading** (top toolbar) so it turns green.
- Make sure **AutoTrading** is enabled in **Tools → Options → Expert Advisors**.

## 4) Attach EA to Chart
1. Open a chart for your symbol (e.g., XAUUSD).
2. Set timeframe to **H1**.
3. Drag **Mad_Rabbit_Bot** onto the chart.
4. Load the matching preset file (see next section).

## 5) Load Preset Files
Use the included presets:
- `XAUUSD.set` (Gold)
- `XAGUSD.set` (Silver)
- `EURUSD.set` (Major)
- `GBPUSD.set` (Major)

Steps:
1. On the EA settings window, click **Load**.
2. Select the preset for your symbol.
3. Click **OK**.

## 6) Recommended First Run
- Start on **demo** for 2–4 weeks.
- Review log files in **/Files/**:
  - `MadRabbit_Decisions.csv`
  - `MadRabbit_Trades.csv`
- Confirm:
  - Low drawdown
  - Few trades per day
  - Respect for daily caps

## 7) VPS Setup (24/7)
1. Install MT5 on your VPS.
2. Log in to your demo/live account.
3. Attach EA to H1 charts.
4. Keep MT5 running (disable sleep/auto‑logout).

## Troubleshooting
- **No trades?** Check session time, spread, and score threshold.
- **EA not running?** Algo Trading is off or chart not H1.
- **Logs missing?** Check MT5 “Files” directory.

## Safety Notes
- No martingale, no grid.
- Daily profit cap stops new trades.
- Daily loss and max drawdown stop new trades.

---
If you need support, send:
- Screenshot of MT5 chart + settings
- `MadRabbit_Decisions.csv`
- `MadRabbit_Trades.csv`
