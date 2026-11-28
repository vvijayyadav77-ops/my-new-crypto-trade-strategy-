const DATA_URL = "data/trading_data.json";

let state = {};

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

  if (Number(value) > 0) {
    el.classList.add("positive");
  }

  if (Number(value) < 0) {
    el.classList.add("negative");
  }
}

function renderPositions() {

  const body = document.getElementById("positions");

  const positions = state.positions || {};

  const entries = Object.values(positions);

  body.innerHTML = "";

  if (!entries.length) {
    body.innerHTML =
      '<tr><td colspan="7" class="empty">No open positions.</td></tr>';

    return;
  }

  entries.forEach(p => {

    const price = Number(p.current_price_inr || 0);

    const entry = Number(p.entry_price_inr || 0);

    const qty = Number(p.qty || 0);

    const pnl = (price - entry) * qty;

    const market = price * qty;

    const tr = document.createElement("tr");

    const values = [
      p.symbol,
      num(qty, 8),
      money(entry),
      money(price),
      money(market),
      money(pnl),
      num(p.score)
    ];

    values.forEach((value, index) => {

      const td = document.createElement("td");

      td.textContent = value;

      if (index === 5) {
        colorize(td, pnl);
      }

      tr.appendChild(td);

    });

    body.appendChild(tr);

  });

}

function renderMomentum() {

  const body = document.getElementById("momentum");

  const coins = state.top_momentum_coins || [];

  body.innerHTML = "";

  if (!coins.length) {

    body.innerHTML =
      '<tr><td colspan="9" class="empty">Waiting for scanner...</td></tr>';

    return;
  }

  coins.forEach((coin, index) => {

    const tr = document.createElement("tr");

    const signal = coin.bullish ? "BUY" : "HOLD";

    const values = [
      index + 1,
      coin.symbol,
      money(coin.price_inr),
      num(coin.rsi),
      num(coin.momentum_3) + "%",
      num(coin.momentum_6) + "%",
      num(coin.volume_ratio) + "x",
      num(coin.score),
      signal
    ];

    values.forEach((value, i) => {

      const td = document.createElement("td");

      td.textContent = value;

      if (i === 8 && coin.bullish) {
        td.className = "positive";
      }

      if (i === 8 && !coin.bullish) {
        td.className = "negative";
      }

      tr.appendChild(td);

    });

    body.appendChild(tr);

  });

}

function renderTrades() {

  const body = document.getElementById("trades");

  const trades = state.trades || [];

  body.innerHTML = "";

  if (!trades.length) {

    body.innerHTML =
      '<tr><td colspan="8" class="empty">No trades yet.</td></tr>';

    return;
  }

  trades.forEach(t => {

    const tr = document.createElement("tr");

    const values = [

      t.time
        ? new Date(t.time).toLocaleString()
        : "—",

      t.symbol || "—",

      t.side || "—",

      money(t.price_inr),

      num(t.qty, 8),

      money(t.fee_inr),

      money(t.pnl_inr),

      t.reason || "—"

    ];

    values.forEach((value, index) => {

      const td = document.createElement("td");

      td.textContent = value;

      if (index === 2) {
        td.className =
          t.side === "BUY" ? "positive" : "negative";
      }

      if (index === 6) {
        colorize(td, t.pnl_inr);
      }

      tr.appendChild(td);

    });

    body.appendChild(tr);

  });

}

function renderDashboard() {

  if (state.cash_inr === undefined) return;

  const cash = Number(state.cash_inr || 0);

  const equity = Number(state.equity_inr || 0);

  const initial = Number(
    state.initial_balance_inr || 10000
  );

  const totalPnl = Number(state.total_pnl_inr || 0);

  const realized = Number(state.realized_pnl_inr || 0);

  const unrealized = Number(state.unrealized_pnl_inr || 0);

  const positions = state.positions || {};

  const openCount = Object.keys(positions).length;

  set("equity", money(equity));

  set("totalPnl", money(totalPnl));

  set("cash", money(cash));

  set("realized", money(realized));

  set("unrealized", money(unrealized));

  set("fees", money(state.total_fees_inr));

  colorize(
    document.getElementById("totalPnl"),
    totalPnl
  );

  colorize(
    document.getElementById("realized"),
    realized
  );

  colorize(
    document.getElementById("unrealized"),
    unrealized
  );

  const pct = initial
    ? totalPnl / initial * 100
    : 0;

  set(
    "pnlPct",
    (pct >= 0 ? "+" : "") + num(pct) + "% since start"
  );

  set("winRate", num(state.win_rate) + "%");

  set(
    "tradeCount",
    (state.total_trades || 0) + " closed trades"
  );

  set("openCount", openCount + " / 3");

  set(
    "positionSide",
    openCount > 0 ? openCount + " OPEN" : "NONE"
  );

  set("scannedCoins", state.scanned_coins || 0);

  set("botMessage", state.status || "Paper bot running.");

  set(
    "updated",
    state.updated_at
      ? new Date(state.updated_at).toLocaleString()
      : "—"
  );

  set(
    "botStatus",
    "PAPER BOT ACTIVE"
  );

  renderPositions();

  renderMomentum();

  renderTrades();

}

async function loadDashboard() {

  try {

    const response = await fetch(
      DATA_URL + "?t=" + Date.now(),
      {
        cache: "no-store"
      }
    );

    if (!response.ok) {
      throw new Error("Trading data not found");
    }

    state = await response.json();

    renderDashboard();

  } catch (error) {

    set("botStatus", "Waiting for bot data");

    set("botMessage", error.message);

  }

}

loadDashboard();

setInterval(loadDashboard, 30000);