import json
import os
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

DATA_FILE = Path("data/trading_data.json")
SYMBOL = "BTCUSDT"
INTERVAL = "5m"
INITIAL_BALANCE_INR = 10000.0
USDT_INR = float(os.getenv("USDT_INR", "90"))  # Approximate display/conversion rate; change if needed.
FEE_RATE = 0.001  # 0.1% paper-trading fee per side
STOP_LOSS_PCT = 0.015
TAKE_PROFIT_PCT = 0.03
POSITION_FRACTION = 0.95
API_BASE = os.getenv("BINANCE_BASE_URL", "https://data-api.binance.vision")

def api_get(path, params=None):
    query = urllib.parse.urlencode(params or {})
    url = f"{API_BASE}{path}" + (f"?{query}" if query else "")
    req = urllib.request.Request(url, headers={"User-Agent": "GitHub-Paper-Trading-Bot/1.0"})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))

def ema(values, period):
    alpha = 2 / (period + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append(alpha * value + (1 - alpha) * result[-1])
    return result

def rsi(values, period=14):
    gains, losses = [], []
    for i in range(1, len(values)):
        change = values[i] - values[i-1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    out = [50.0] * period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rs = avg_gain / avg_loss if avg_loss else 999999
        out.append(100 - (100 / (1 + rs)))
    return out

def macd(values):
    fast, slow = ema(values, 12), ema(values, 26)
    line = [a-b for a, b in zip(fast, slow)]
    signal = ema(line, 9)
    return line, signal

def supertrend_direction(highs, lows, closes, period=10, multiplier=3.0):
    trs = []
    for i in range(len(closes)):
        if i == 0:
            trs.append(highs[i] - lows[i])
        else:
            trs.append(max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1])))
    atr = [sum(trs[:period]) / period]
    for tr in trs[period:]:
        atr.append((atr[-1] * (period-1) + tr) / period)
    offset = len(closes) - len(atr)
    upper, lower = [], []
    for j, a in enumerate(atr):
        i = j + offset
        mid = (highs[i] + lows[i]) / 2
        upper.append(mid + multiplier*a)
        lower.append(mid - multiplier*a)
    direction = 1
    final_upper, final_lower = upper[0], lower[0]
    for j in range(1, len(atr)):
        i = j + offset
        prev_close = closes[i-1]
        final_upper = upper[j] if (upper[j] < final_upper or prev_close > final_upper) else final_upper
        final_lower = lower[j] if (lower[j] > final_lower or prev_close < final_lower) else final_lower
        if direction == 1 and closes[i] < final_lower:
            direction = -1
        elif direction == -1 and closes[i] > final_upper:
            direction = 1
    return direction

def default_state():
    return {
        "initial_balance_inr": INITIAL_BALANCE_INR,
        "cash_inr": INITIAL_BALANCE_INR,
        "btc_qty": 0.0,
        "entry_price_inr": None,
        "entry_fee_inr": 0.0,
        "trades": [],
        "last_processed_candle": None,
        "updated_at": None,
        "status": "Waiting for first signal",
        "strategy": "EMA 9/21 + RSI 14 + MACD 12/26/9 + Supertrend 10/3",
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "usdt_inr": USDT_INR,
        "fee_rate": FEE_RATE
    }

def load_state():
    if DATA_FILE.exists():
        try:
            state = json.loads(DATA_FILE.read_text())
            if "trades" in state and "cash_inr" in state:
                return state
        except Exception:
            pass
    return default_state()

def save_state(state):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(state, indent=2))

def main():
    state = load_state()
    klines = api_get("/api/v3/klines", {"symbol": SYMBOL, "interval": INTERVAL, "limit": 200})
    # Ignore the currently forming candle; trade only after a 5-minute candle closes.
    closed = klines[:-1]
    closes_usdt = [float(k[4]) for k in closed]
    highs_usdt = [float(k[2]) for k in closed]
    lows_usdt = [float(k[3]) for k in closed]
    candle_id = int(closed[-1][0])
    price_inr = closes_usdt[-1] * USDT_INR

    fast_ema, slow_ema = ema(closes_usdt, 9), ema(closes_usdt, 21)
    rsi_values = rsi(closes_usdt, 14)
    macd_line, macd_signal = macd(closes_usdt)
    st_direction = supertrend_direction(highs_usdt, lows_usdt, closes_usdt, 10, 3.0)

    buy_signal = (
        fast_ema[-1] > slow_ema[-1]
        and rsi_values[-1] >= 50
        and macd_line[-1] > macd_signal[-1]
        and st_direction == 1
    )
    sell_signal = (
        fast_ema[-1] < slow_ema[-1]
        and rsi_values[-1] <= 50
        and macd_line[-1] < macd_signal[-1]
        and st_direction == -1
    )

    state["current_price_inr"] = price_inr
    state["current_price_usdt"] = closes_usdt[-1]
    state["indicators"] = {
        "ema9": fast_ema[-1] * USDT_INR,
        "ema21": slow_ema[-1] * USDT_INR,
        "rsi14": rsi_values[-1],
        "macd": macd_line[-1],
        "macd_signal": macd_signal[-1],
        "supertrend": "BULLISH" if st_direction == 1 else "BEARISH"
    }
    state["signal"] = "BUY" if buy_signal else ("SELL" if sell_signal else "HOLD")

    if state.get("last_processed_candle") != candle_id:
        qty = float(state.get("btc_qty", 0))
        if qty > 0:
            entry = float(state["entry_price_inr"])
            change = (price_inr - entry) / entry
            exit_reason = None
            if change <= -STOP_LOSS_PCT:
                exit_reason = "Stop Loss"
            elif change >= TAKE_PROFIT_PCT:
                exit_reason = "Take Profit"
            elif sell_signal:
                exit_reason = "Sell Signal"
            if exit_reason:
                gross = qty * price_inr
                exit_fee = gross * FEE_RATE
                proceeds = gross - exit_fee
                state["cash_inr"] += proceeds
                entry_value = qty * entry
                pnl = proceeds - entry_value - float(state.get("entry_fee_inr", 0))
                state["trades"].insert(0, {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "side": "SELL",
                    "price_inr": price_inr,
                    "qty_btc": qty,
                    "fee_inr": exit_fee,
                    "pnl_inr": pnl,
                    "reason": exit_reason
                })
                state["btc_qty"] = 0.0
                state["entry_price_inr"] = None
                state["entry_fee_inr"] = 0.0
                state["status"] = f"Position closed: {exit_reason}"
        elif buy_signal:
            spend = state["cash_inr"] * POSITION_FRACTION
            fee = spend * FEE_RATE
            qty = (spend - fee) / price_inr
            if qty > 0:
                state["cash_inr"] -= spend
                state["btc_qty"] = qty
                state["entry_price_inr"] = price_inr
                state["entry_fee_inr"] = fee
                state["trades"].insert(0, {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "side": "BUY",
                    "price_inr": price_inr,
                    "qty_btc": qty,
                    "fee_inr": fee,
                    "pnl_inr": 0.0,
                    "reason": "All indicators bullish"
                })
                state["status"] = "Paper BUY opened"
        state["last_processed_candle"] = candle_id

    state["trades"] = state.get("trades", [])[:100]
    qty = float(state.get("btc_qty", 0))
    market_value = qty * price_inr
    unrealized = (price_inr - float(state["entry_price_inr"])) * qty if qty else 0.0
    equity = float(state["cash_inr"]) + market_value
    closed_pnl = sum(float(t.get("pnl_inr", 0)) for t in state["trades"] if t.get("side") == "SELL")
    total_fees = sum(float(t.get("fee_inr", 0)) for t in state["trades"])
    wins = sum(1 for t in state["trades"] if t.get("side") == "SELL" and float(t.get("pnl_inr", 0)) > 0)
    losses = sum(1 for t in state["trades"] if t.get("side") == "SELL" and float(t.get("pnl_inr", 0)) <= 0)
    closed_count = wins + losses
    state.update({
        "cash_inr": round(float(state["cash_inr"]), 4),
        "market_value_inr": round(market_value, 4),
        "equity_inr": round(equity, 4),
        "available_balance_inr": round(float(state["cash_inr"]), 4),
        "unrealized_pnl_inr": round(unrealized, 4),
        "realized_pnl_inr": round(closed_pnl, 4),
        "total_pnl_inr": round(equity - INITIAL_BALANCE_INR, 4),
        "total_fees_inr": round(total_fees, 4),
        "total_trades": closed_count,
        "win_rate": round((wins / closed_count * 100) if closed_count else 0, 2),
        "open_position": {
            "side": "BUY" if qty else "NONE",
            "qty_btc": qty,
            "entry_price_inr": state.get("entry_price_inr"),
            "market_value_inr": round(market_value, 4)
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status": state.get("status", "Running")
    })
    save_state(state)
    print(f"Updated paper bot. Signal={state['signal']} Equity=₹{equity:.2f}")

if __name__ == "__main__":
    main()
