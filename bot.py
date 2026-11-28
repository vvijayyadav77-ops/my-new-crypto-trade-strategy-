import json
import os
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

DATA_FILE = Path("data/trading_data.json")

INTERVAL = "5m"
MAX_COINS = 100
MAX_OPEN_POSITIONS = 3

INITIAL_BALANCE_INR = 10000.0
USDT_INR = float(os.getenv("USDT_INR", "90"))

FEE_RATE = 0.001
STOP_LOSS_PCT = 0.015
TAKE_PROFIT_PCT = 0.03

POSITION_FRACTION = 0.95

CHECK_INTERVAL = 60

API_BASE = os.getenv(
    "BINANCE_BASE_URL",
    "https://data-api.binance.vision"
)

EXCLUDED = {
    "USDCUSDT", "FDUSDUSDT", "TUSDUSDT",
    "USDPUSDT", "DAIUSDT", "EURUSDT",
    "BTTCUSDT"
}


def api_get(path, params=None):
    query = urllib.parse.urlencode(params or {})
    url = f"{API_BASE}{path}" + (
        f"?{query}" if query else ""
    )

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Momentum-Paper-Bot/1.0"}
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode())


def ema(values, period):
    alpha = 2 / (period + 1)
    result = [values[0]]

    for value in values[1:]:
        result.append(
            alpha * value + (1 - alpha) * result[-1]
        )

    return result


def rsi(values, period=14):
    gains = []
    losses = []

    for i in range(1, len(values)):
        change = values[i] - values[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    result = [50.0] * period

    for i in range(period, len(gains)):
        avg_gain = (
            avg_gain * (period - 1) + gains[i]
        ) / period

        avg_loss = (
            avg_loss * (period - 1) + losses[i]
        ) / period

        rs = avg_gain / avg_loss if avg_loss else 999999

        result.append(100 - (100 / (1 + rs)))

    return result


def macd(values):
    fast = ema(values, 12)
    slow = ema(values, 26)

    line = [a - b for a, b in zip(fast, slow)]
    signal = ema(line, 9)

    return line, signal


def get_top_coins():

    data = api_get("/api/v3/ticker/24hr")

    exchange = api_get("/api/v3/exchangeInfo")

    allowed = {
        item["symbol"]
        for item in exchange["symbols"]
        if item["status"] == "TRADING"
        and item["quoteAsset"] == "USDT"
        and item["isSpotTradingAllowed"]
    }

    coins = []

    for item in data:

        symbol = item["symbol"]

        if symbol not in allowed:
            continue

        if symbol in EXCLUDED:
            continue

        if any(
            symbol.startswith(x)
            for x in ("UP", "DOWN", "BULL", "BEAR")
        ):
            continue

        volume = float(item["quoteVolume"])

        if volume < 1000000:
            continue

        coins.append({
            "symbol": symbol,
            "volume": volume
        })

    coins.sort(
        key=lambda x: x["volume"],
        reverse=True
    )

    return coins[:MAX_COINS]


def analyze_coin(symbol):

    klines = api_get(
        "/api/v3/klines",
        {
            "symbol": symbol,
            "interval": INTERVAL,
            "limit": 100
        }
    )

    if len(klines) < 50:
        return None

    closed = klines[:-1]

    closes = [float(x[4]) for x in closed]
    volumes = [float(x[5]) for x in closed]

    price = closes[-1]

    fast = ema(closes, 9)
    slow = ema(closes, 21)

    rsi_values = rsi(closes)
    macd_line, macd_signal = macd(closes)

    if price <= 0:
        return None

    momentum_3 = (
        (price / closes[-4]) - 1
    ) * 100

    momentum_6 = (
        (price / closes[-7]) - 1
    ) * 100

    volume_avg = sum(volumes[-21:-1]) / 20

    volume_ratio = (
        volumes[-1] / volume_avg
        if volume_avg > 0 else 0
    )

    current_rsi = rsi_values[-1]

    bullish = (
        fast[-1] > slow[-1]
        and macd_line[-1] > macd_signal[-1]
        and current_rsi >= 52
        and current_rsi <= 75
        and momentum_3 > 0
        and momentum_6 > 0
    )

    bearish = (
        fast[-1] < slow[-1]
        and macd_line[-1] < macd_signal[-1]
        and current_rsi < 48
    )

    score = 0

    if fast[-1] > slow[-1]:
        score += 25

    if macd_line[-1] > macd_signal[-1]:
        score += 20

    if 52 <= current_rsi <= 75:
        score += 15

    if momentum_3 > 0:
        score += min(momentum_3 * 5, 15)

    if momentum_6 > 0:
        score += min(momentum_6 * 3, 15)

    if volume_ratio >= 1.2:
        score += 10

    return {
        "symbol": symbol,
        "price_usdt": price,
        "price_inr": price * USDT_INR,
        "rsi": current_rsi,
        "momentum_3": momentum_3,
        "momentum_6": momentum_6,
        "volume_ratio": volume_ratio,
        "score": round(score, 2),
        "bullish": bullish,
        "bearish": bearish,
        "candle_id": int(closed[-1][0])
    }


def default_state():

    return {
        "initial_balance_inr": INITIAL_BALANCE_INR,
        "cash_inr": INITIAL_BALANCE_INR,
        "btc_qty": 0.0,
        "entry_price_inr": None,
        "entry_fee_inr": 0.0,
        "positions": {},
        "trades": [],
        "last_processed_candle": None,
        "updated_at": None,
        "status": "Scanning Momentum Coins",
        "strategy": "Top 100 Multi-Coin Momentum Strategy",
        "symbol": "MULTI",
        "interval": INTERVAL,
        "usdt_inr": USDT_INR,
        "fee_rate": FEE_RATE
    }


def load_state():

    if DATA_FILE.exists():

        try:
            state = json.loads(DATA_FILE.read_text())

            if "positions" not in state:
                state["positions"] = {}

            if "trades" not in state:
                state["trades"] = []

            if "cash_inr" not in state:
                state["cash_inr"] = INITIAL_BALANCE_INR

            if "initial_balance_inr" not in state:
                state["initial_balance_inr"] = INITIAL_BALANCE_INR

            return state

        except Exception as error:
            print("State error:", error)

    return default_state()


def save_state(state):

    DATA_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temp = DATA_FILE.with_suffix(".tmp")

    temp.write_text(
        json.dumps(state, indent=2)
    )

    temp.replace(DATA_FILE)


def open_position(state, coin):

    positions = state["positions"]

    if len(positions) >= MAX_OPEN_POSITIONS:
        return

    symbol = coin["symbol"]

    if symbol in positions:
        return

    equity = float(state["cash_inr"])

    for position in positions.values():
        equity += (
            position["qty"] * position["current_price_inr"]
        )

    spend = min(
        float(state["cash_inr"]),
        equity * POSITION_FRACTION / MAX_OPEN_POSITIONS
    )

    if spend < 100:
        return

    price = coin["price_inr"]

    fee = spend * FEE_RATE

    qty = (spend - fee) / price

    if qty <= 0:
        return

    state["cash_inr"] -= spend

    positions[symbol] = {
        "symbol": symbol,
        "qty": qty,
        "entry_price_inr": price,
        "current_price_inr": price,
        "entry_fee_inr": fee,
        "score": coin["score"],
        "entry_time": datetime.now(timezone.utc).isoformat()
    }

    state["trades"].insert(0, {
        "time": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "side": "BUY",
        "price_inr": price,
        "qty": qty,
        "fee_inr": fee,
        "pnl_inr": 0,
        "reason": "Strong Momentum"
    })

    state["status"] = f"BUY: {symbol}"


def close_position(state, symbol, price, reason):

    position = state["positions"].get(symbol)

    if not position:
        return

    qty = position["qty"]

    gross = qty * price

    exit_fee = gross * FEE_RATE

    proceeds = gross - exit_fee

    entry_value = qty * position["entry_price_inr"]

    pnl = (
        proceeds
        - entry_value
        - position["entry_fee_inr"]
    )

    state["cash_inr"] += proceeds

    state["trades"].insert(0, {
        "time": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "side": "SELL",
        "price_inr": price,
        "qty": qty,
        "fee_inr": exit_fee,
        "pnl_inr": pnl,
        "reason": reason
    })

    del state["positions"][symbol]

    state["status"] = f"SELL: {symbol} - {reason}"


def process_once():

    state = load_state()

    print("Scanning top 100 coins...", flush=True)

    coins = get_top_coins()

    analyzed = []

    for coin in coins:

        try:

            result = analyze_coin(coin["symbol"])

            if result:
                analyzed.append(result)

        except Exception as error:

            print(
                f"Skipping {coin['symbol']}: {error}",
                flush=True
            )

        time.sleep(0.05)

    if not analyzed:
        raise ValueError("No coins analyzed successfully")

    analyzed.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    state["scanned_coins"] = len(analyzed)

    state["top_momentum_coins"] = analyzed[:10]

    latest_candle = max(
        x["candle_id"] for x in analyzed
    )

    new_candle = (
        state.get("last_processed_candle")
        != latest_candle
    )

    # Update existing positions.

    for symbol in list(state["positions"].keys()):

        position = state["positions"][symbol]

        coin = next(
            (x for x in analyzed if x["symbol"] == symbol),
            None
        )

        if coin is None:
            continue

        price = coin["price_inr"]

        position["current_price_inr"] = price
        position["score"] = coin["score"]

        entry = position["entry_price_inr"]

        change = (price - entry) / entry

        reason = None

        if change <= -STOP_LOSS_PCT:
            reason = "Stop Loss"

        elif change >= TAKE_PROFIT_PCT:
            reason = "Take Profit"

        elif new_candle and coin["bearish"]:
            reason = "Momentum Reversal"

        if reason:

            close_position(
                state,
                symbol,
                price,
                reason
            )

    # Buy strongest momentum coins.

    if new_candle:

        candidates = [
            x for x in analyzed
            if x["bullish"]
            and x["score"] >= 65
        ]

        for coin in candidates:

            if len(state["positions"]) >= MAX_OPEN_POSITIONS:
                break

            open_position(state, coin)

        state["last_processed_candle"] = latest_candle

    # Portfolio calculations.

    market_value = sum(
        p["qty"] * p["current_price_inr"]
        for p in state["positions"].values()
    )

    unrealized = sum(
        (
            p["current_price_inr"] - p["entry_price_inr"]
        ) * p["qty"]
        for p in state["positions"].values()
    )

    equity = state["cash_inr"] + market_value

    closed_trades = [
        t for t in state["trades"]
        if t["side"] == "SELL"
    ]

    wins = sum(
        1 for t in closed_trades
        if t["pnl_inr"] > 0
    )

    losses = sum(
        1 for t in closed_trades
        if t["pnl_inr"] <= 0
    )

    closed_pnl = sum(
        t["pnl_inr"] for t in closed_trades
    )

    fees = sum(
        t.get("fee_inr", 0)
        for t in state["trades"]
    )

    # Dashboard compatibility.

    btc_position = state["positions"].get("BTCUSDT", {})

    state.update({

        "cash_inr": round(state["cash_inr"], 4),

        "market_value_inr": round(market_value, 4),

        "equity_inr": round(equity, 4),

        "available_balance_inr": round(state["cash_inr"], 4),

        "unrealized_pnl_inr": round(unrealized, 4),

        "realized_pnl_inr": round(closed_pnl, 4),

        "total_pnl_inr": round(
            equity - state["initial_balance_inr"], 4
        ),

        "total_fees_inr": round(fees, 4),

        "total_trades": len(closed_trades),

        "win_rate": round(
            wins / len(closed_trades) * 100
            if closed_trades else 0,
            2
        ),

        "open_positions": len(state["positions"]),

        "open_position": {
            "side": "BUY" if state["positions"] else "NONE",
            "qty_btc": btc_position.get("qty", 0),
            "entry_price_inr": btc_position.get("entry_price_inr"),
            "market_value_inr": round(market_value, 4)
        },

        "positions": state["positions"],

        "updated_at": datetime.now(timezone.utc).isoformat()

    })

    state["trades"] = state["trades"][:100]

    save_state(state)

    print(
        f"Scanned={len(analyzed)} "
        f"Open={len(state['positions'])} "
        f"Cash=₹{state['cash_inr']:.2f} "
        f"Equity=₹{equity:.2f} "
        f"PNL=₹{equity - state['initial_balance_inr']:.2f}",
        flush=True
    )


def main():

    print(
        "Multi-Coin Momentum Paper Trading Bot Started",
        flush=True
    )

    while True:

        try:

            process_once()

        except KeyboardInterrupt:

            print("Bot stopped.", flush=True)
            break

        except Exception as error:

            print("Bot Error:", error, flush=True)

        print(
            f"Next scan in {CHECK_INTERVAL} seconds...",
            flush=True
        )

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()