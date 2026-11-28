const DATA_URL = "data/trading_data.json";
const WS_URL = "wss://data-stream.binance.vision:443/ws/btcusdt@trade";

let state = {};
let livePriceUSDT = 0;
let socket = null;
let reconnectTimer = null;

const money = n =>
  "₹" + Number(n || 0).toLocaleString("en-IN", {
    maximumFractionDigits: 2
  });

const num = (n, d = 2) =>
  Number(n || 0).toLocaleString("en-IN", {
    maximumFractionDigits: d
  });

function set(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function colorize(el, value) {
  if (!el) return;

  el.classList.remove("positive", "negative");

  if (value > 0) el.classList.add("positive");
  if (value < 0) el.classList.add("negative");
}

function renderDashboard() {
  if (!state.cash_inr && state.cash_inr !== 0) return;

  const rate = Number(state.usdt_inr || 90);
  const priceUSDT = livePriceUSDT || Number(state.current_price_usdt || 0);
  const priceINR = priceUSDT * rate;

  const qty = Number(state.btc_qty || 0);
  const cash = Number(state.cash_inr || 0);
  const marketValue = qty * priceINR;

  const unrealized = qty > 0
    ? (priceINR - Number(state.entry_price_inr || 0)) * qty
    : 0;

  const equity = cash + marketValue;
  const initial = Number(state.initial_balance_inr || 10000);
  const totalPnl = equity - initial;

  set("price", money(priceINR));
  set("priceUsdt", "$" + num(priceUSDT, 2) + " USDT");

  set("equity", money(equity));
  set("totalPnl", money(totalPnl));

  colorize(document.getElementById("totalPnl"), totalPnl);

  const pct = initial ? totalPnl / initial * 100 : 0;

  set("pnlPct", (pct >= 0 ? "+" : "") + num(pct) + "% since start");

  set("cash", money(cash));
  set("realized", money(state.realized_pnl_inr));
  set("unrealized", money(unrealized));
  set("fees", money(state.total_fees_inr));

  colorize(document.getElementById("realized"), state.realized_pnl_inr);
  colorize(document.getElementById("unrealized"), unrealized);

  set("winRate", num(state.win_rate) + "%");
  set("tradeCount", (state.total_trades || 0) + " closed trades");

  set("positionSide", qty > 0 ? "BUY" : "NONE");
  set("qty", num(qty, 8) + " BTC");

  set(
    "entry",
    state.entry_price_inr ? money(state.entry_price_inr) : "—"
  );

  set("marketValue", money(marketValue));

  set("signal", state.signal || "—");

  const i = state.indicators || {};

  set("ema", money(i.ema9) + " / " + money(i.ema21));
  set("rsi", num(i.rsi14));
  set("macd", num(i.macd, 5) + " / " + num(i.macd_signal, 5));
  set("supertrend", i.supertrend || "—");

  set("botMessage", state.status || "Paper bot running.");

  set("updated", "Live price: " + new Date().toLocaleTimeString());
}

async function loadDashboard() {
  try {
    const response = await fetch(
      DATA_URL + "?t=" + Date.now(),
      { cache: "no-store" }
    );

    if (!response.ok) {
      throw new Error("Trading data not found");
    }

    state = await response.json();

    if (!livePriceUSDT) {
      livePriceUSDT = Number(state.current_price_usdt || 0);
    }

    set("botStatus", "Connecting live market...");
    renderDashboard();

    const body = document.getElementById("trades");
    body.innerHTML = "";

    (state.trades || []).forEach(t => {
      const tr = document.createElement("tr");

      const values = [
        t.time ? new Date(t.time).toLocaleString() : "—",
        t.side || "—",
        money(t.price_inr),
        num(t.qty_btc, 8),
        money(t.fee_inr),
        money(t.pnl_inr),
        t.reason || "—"
      ];

      values.forEach((v, index) => {
        const td = document.createElement("td");
        td.textContent = v;

        if (index === 1) {
          td.className = t.side === "BUY" ? "positive" : "negative";
        }

        if (index === 5) {
          colorize(td, t.pnl_inr);
        }

        tr.appendChild(td);
      });

      body.appendChild(tr);
    });

    if (!(state.trades || []).length) {
      body.innerHTML =
        '<tr><td colspan="7" class="empty">No trades yet.</td></tr>';
    }

  } catch (error) {
    set("botStatus", "Waiting for bot data");
    set("botMessage", error.message);
  }
}

function connectWebSocket() {
  if (socket) {
    socket.close();
  }

  socket = new WebSocket(WS_URL);

  socket.onopen = () => {
    set("botStatus", "LIVE BTC CONNECTED");
    document.querySelector(".dot").style.background = "#31d0a0";
  };

  socket.onmessage = event => {
    try {
      const data = JSON.parse(event.data);

      livePriceUSDT = Number(data.p);

      renderDashboard();

    } catch (error) {
      console.error("Price update error:", error);
    }
  };

  socket.onerror = () => {
    set("botStatus", "WebSocket connection error");
  };

  socket.onclose = () => {
    set("botStatus", "Reconnecting...");
    document.querySelector(".dot").style.background = "#eab308";

    clearTimeout(reconnectTimer);

    reconnectTimer = setTimeout(connectWebSocket, 3000);
  };
}

loadDashboard();
connectWebSocket();

// Refresh saved trading data every 30 seconds.
setInterval(loadDashboard, 30000);