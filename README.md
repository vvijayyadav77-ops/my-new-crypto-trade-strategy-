# Binance Spot Paper Trading Bot

A GitHub Actions-hosted **paper trading** bot for BTC/USDT with a static HTML dashboard.

## Files
- `bot.py`: paper trading engine; does not send real orders.
- `index.html`, `style.css`, `script.js`: GitHub Pages dashboard.
- `data/trading_data.json`: dashboard data written by the bot.
- `.github/workflows/paper-bot.yml`: runs every 5 minutes and commits updated data.

## Install
1. Upload all files and folders to the root of your GitHub repository.
2. Ensure the default branch is `main`.
3. In **Settings → Actions → General → Workflow permissions**, select **Read and write permissions** and save.
4. Open **Actions → Binance Spot Paper Bot → Run workflow** once.
5. In **Settings → Pages**, choose **Deploy from a branch**, branch `main`, folder `/(root)`, then Save.
6. Open the Pages URL shown there. The dashboard reads `data/trading_data.json`.

## Important
- This is paper trading only. It does not use API keys and cannot place real Binance orders.
- The bot uses public Binance market candles. If Binance returns a regional/API error (such as HTTP 451), the workflow may fail; no trade is simulated on that failed run.
- Starting virtual capital is ₹10,000.
- `USDT_INR` defaults to 90 as an approximate conversion assumption, not a live FX quote. Change the default in `bot.py` or set the environment variable if you want another estimate.
- The 0.1% fee is an illustrative paper-trading assumption; actual fees depend on account tier and fee discounts.
- GitHub scheduled workflows are not guaranteed to run at the exact minute and may be delayed.
- Strategy signals are educational and do not guarantee profit. Review the code before using it.
