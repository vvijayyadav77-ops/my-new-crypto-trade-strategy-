# Binance BTC Paper Trading Bot + Dashboard

This project is **paper trading only**. It reads public BTC/USDT market candles from Binance and simulates orders locally. It does not place real orders and needs no API key or secret.

## Included
- Starting virtual balance: 10,000 USDT
- BTC/USDT, 5-minute closed candles
- EMA 9/21 crossover entry/exit
- 1% stop loss and 2% take profit
- Illustrative 0.1% fee per side
- 10% of available cash allocated per entry
- Persistent state and CSV trade history
- Static HTML dashboard

## Upload to GitHub
1. Extract this ZIP.
2. Upload all files and folders to the root of your new repository. Make sure the `.github/workflows/paper-bot.yml` file is included.
3. Commit to the `main` branch.
4. Open **Actions** in the repository, select **Binance BTC Paper Bot**, and click **Run workflow** once.
5. In repository **Settings → Pages**, set **Deploy from a branch**, choose `main` and `/ (root)`, then Save.
6. After Pages publishes, open the Pages URL to see `index.html`. The dashboard reads `data/state.json` and `data/trades.csv` committed by the workflow.

## Important
- GitHub scheduled jobs are not guaranteed to start at the exact minute and may be delayed.
- The dashboard updates when the Action commits new data; refresh the page if needed.
- The fee is an assumption for simulation, not a statement of your Binance fee tier.
- This simple EMA strategy is educational and is not a claim of profitability.
- Do not add Binance API keys or enable real trading for this paper bot.
