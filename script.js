const DATA_URL = "data/trading_data.json";
const money = n => "₹" + Number(n || 0).toLocaleString("en-IN",{maximumFractionDigits:2});
const num = (n,d=2) => Number(n || 0).toLocaleString("en-IN",{maximumFractionDigits:d});
function colorize(el, value){el.classList.remove("positive","negative"); if(value>0)el.classList.add("positive");if(value<0)el.classList.add("negative");}
function set(id,value){const el=document.getElementById(id);if(el)el.textContent=value;}
async function loadDashboard(){
  try{
    const res=await fetch(DATA_URL+"?t="+Date.now(),{cache:"no-store"});
    if(!res.ok)throw new Error("Dashboard data not found yet");
    const d=await res.json();
    set("botStatus",d.updated_at?"Bot data available":"Waiting for bot");
    document.querySelector(".dot").style.background=d.updated_at?"#31d0a0":"#eab308";
    set("price",money(d.current_price_inr));
    set("priceUsdt",d.current_price_usdt?"$"+num(d.current_price_usdt,2)+" USDT":"—");
    set("equity",money(d.equity_inr));set("totalPnl",money(d.total_pnl_inr));colorize(document.getElementById("totalPnl"),d.total_pnl_inr);
    const pct=d.initial_balance_inr?d.total_pnl_inr/d.initial_balance_inr*100:0;
    set("pnlPct",(pct>=0?"+":"")+num(pct)+"% since start");
    set("cash",money(d.available_balance_inr));set("realized",money(d.realized_pnl_inr));colorize(document.getElementById("realized"),d.realized_pnl_inr);
    set("unrealized",money(d.unrealized_pnl_inr));colorize(document.getElementById("unrealized"),d.unrealized_pnl_inr);
    set("fees",money(d.total_fees_inr));set("winRate",num(d.win_rate)+"%");
    set("tradeCount",(d.total_trades||0)+" closed trades");
    set("signal",d.signal||"—");set("updated",d.updated_at?"Updated "+new Date(d.updated_at).toLocaleString():"Not updated");
    set("positionSide",d.open_position?.side||"NONE");set("qty",num(d.open_position?.qty_btc,6)+" BTC");
    set("entry",d.open_position?.entry_price_inr?money(d.open_position.entry_price_inr):"—");
    set("marketValue",money(d.market_value_inr));
    const i=d.indicators||{};set("ema",money(i.ema9)+" / "+money(i.ema21));set("rsi",num(i.rsi14));
    set("macd",num(i.macd,5)+" / "+num(i.macd_signal,5));set("supertrend",i.supertrend||"—");
    set("botMessage",d.status||"Bot is running.");
    const body=document.getElementById("trades");body.innerHTML="";
    (d.trades||[]).forEach(t=>{
      const tr=document.createElement("tr");
      const vals=[t.time?new Date(t.time).toLocaleString():"—",t.side||"—",money(t.price_inr),num(t.qty_btc,6),money(t.fee_inr),money(t.pnl_inr),t.reason||"—"];
      vals.forEach((v,idx)=>{const td=document.createElement("td");td.textContent=v;if(idx===1)td.className=t.side==="BUY"?"positive":"negative";if(idx===5)colorize(td,t.pnl_inr);tr.appendChild(td);});
      body.appendChild(tr);
    });
    if(!(d.trades||[]).length)body.innerHTML='<tr><td colspan="7" class="empty">No trades yet. Waiting for a signal.</td></tr>';
  }catch(e){set("botStatus","Waiting for first bot run");set("botMessage",e.message+" — run the GitHub Actions workflow once.");}
}
loadDashboard();setInterval(loadDashboard,60000);
