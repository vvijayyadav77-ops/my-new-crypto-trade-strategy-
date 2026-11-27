import json, csv, os
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE = "https://data-api.binance.vision"
SYMBOL = "BTCUSDT"
INTERVAL = "5m"
START_BALANCE = 10_000.0
FEE_RATE = 0.001          # illustrative 0.1% per side; change to model your fee tier
POSITION_FRACTION = 0.10  # use 10% of available quote balance per trade
STOP_LOSS = 0.01
TAKE_PROFIT = 0.02

STATE = Path("data/state.json")
TRADES = Path("data/trades.csv")
STATE.parent.mkdir(exist_ok=True)

def get_klines():
    r = requests.get(f"{BASE}/api/v3/klines",
                     params={"symbol": SYMBOL, "interval": INTERVAL, "limit": 100},
                     timeout=20)
    r.raise_for_status()
    rows = r.json()
    # Exclude the currently forming candle.
    return [float(x[4]) for x in rows[:-1]], int(rows[-2][6])

def ema(values, period):
    alpha = 2 / (period + 1)
    value = values[0]
    for x in values[1:]:
        value = alpha * x + (1 - alpha) * value
    return value

def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {
        "initial_balance": START_BALANCE,
        "cash": START_BALANCE,
        "quantity": 0.0,
        "entry_price": None,
        "entry_fee": 0.0,
        "last_candle": 0,
        "last_price": None,
        "realized_pnl": 0.0,
        "fees_paid": 0.0,
        "updated_at": None,
        "status": "Waiting for first signal"
    }

def save_trade(action, price, qty, fee, pnl, reason):
    new_file = not TRADES.exists()
    with TRADES.open("a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["time_utc", "symbol", "action", "price", "quantity", "fee", "realized_pnl", "reason"])
        w.writerow([datetime.now(timezone.utc).isoformat(), SYMBOL, action, f"{price:.2f}",
                    f"{qty:.8f}", f"{fee:.4f}", f"{pnl:.4f}", reason])

def main():
    prices, candle_time = get_klines()
    if len(prices) < 30:
        raise RuntimeError("Not enough candle data yet")
    price = prices[-1]
    fast_now, slow_now = ema(prices[-30:], 9), ema(prices[-60:], 21)
    fast_prev, slow_prev = ema(prices[-31:-1], 9), ema(prices[-61:-1], 21)

    s = load_state()
    if s["last_candle"] == candle_time:
        print("This closed candle was already processed; no duplicate action.")
        return

    qty = float(s["quantity"])
    entry = s["entry_price"]
    action = None
    reason = "No signal"

    if qty > 0:
        change = price / float(entry) - 1
        if change <= -STOP_LOSS:
            action, reason = "SELL", "Stop loss"
        elif change >= TAKE_PROFIT:
            action, reason = "SELL", "Take profit"
        elif fast_prev >= slow_prev and fast_now < slow_now:
            action, reason = "SELL", "EMA bearish crossover"
    elif fast_prev <= slow_prev and fast_now > slow_now:
        action, reason = "BUY", "EMA bullish crossover"

    if action == "BUY":
        budget = float(s["cash"]) * POSITION_FRACTION
        fee = budget * FEE_RATE
        spend = budget - fee
        qty = spend / price
        s["cash"] -= budget
        s["quantity"] = qty
        s["entry_price"] = price
        s["entry_fee"] = fee
        s["fees_paid"] += fee
        save_trade("BUY", price, qty, fee, 0.0, reason)
        s["status"] = f"Open position — {reason}"

    elif action == "SELL":
        qty = float(s["quantity"])
        gross = qty * price
        fee = gross * FEE_RATE
        proceeds = gross - fee
        entry_cost = qty * float(s["entry_price"]) + float(s["entry_fee"])
        pnl = proceeds - entry_cost
        s["cash"] += proceeds
        s["realized_pnl"] += pnl
        s["fees_paid"] += fee
        save_trade("SELL", price, qty, fee, pnl, reason)
        s["quantity"] = 0.0
        s["entry_price"] = None
        s["entry_fee"] = 0.0
        s["status"] = f"Position closed — {reason}"

    s["last_candle"] = candle_time
    s["last_price"] = price
    s["updated_at"] = datetime.now(timezone.utc).isoformat()
    market_value = float(s["quantity"]) * price
    equity = float(s["cash"]) + market_value
    s["unrealized_pnl"] = ((price / float(s["entry_price"]) - 1) * float(s["quantity"]) * float(s["entry_price"])
                            - float(s["entry_fee"])) if s["quantity"] > 0 else 0.0
    s["equity"] = equity
    s["total_pnl"] = equity - float(s["initial_balance"])
    s["market_value"] = market_value
    s["symbol"] = SYMBOL
    s["strategy"] = "EMA 9/21 crossover; 5-minute candles"
    s["fee_rate"] = FEE_RATE
    s["position_fraction"] = POSITION_FRACTION
    s["stop_loss_pct"] = STOP_LOSS * 100
    s["take_profit_pct"] = TAKE_PROFIT * 100
    STATE.write_text(json.dumps(s, indent=2))
    print(json.dumps({"price": price, "status": s["status"], "equity": equity}, indent=2))

if __name__ == "__main__":
    main()
