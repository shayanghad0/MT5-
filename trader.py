import json
import time
from datetime import datetime
import MetaTrader5 as mt5

# --- Configuration ---
CONCLUSION_FILE = "conclusion.json"
TRADES_FILE = "trades.json"
REPORT_FILE = "report.html"
VOLUME = 0.01
TP_POINTS = 250
SL_POINTS = 50
CHECK_INTERVAL = 0.05              # 50 milliseconds
MAX_WAIT_SECONDS = 3600 * 24       # 24 hours per trade (fallback)
MAX_RUN_SECONDS = 5 * 60           # 5 minutes overall runtime

# ======================================================
# HTML REPORT GENERATOR (built‑in)
# ======================================================

def load_trades(file_path):
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            if not isinstance(data, list):
                return []
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def compute_stats(trades):
    total_trades = len(trades)
    if total_trades == 0:
        return {
            "total": 0, "wins": 0, "losses": 0,
            "total_profit_pts": 0, "total_profit_currency": 0,
            "max_profit_pts": 0, "max_loss_pts": 0,
            "avg_profit_pts": 0, "avg_loss_pts": 0,
            "win_rate": 0,
            "cumulative_pts": []
        }

    profits_pts = []
    profits_cur = []
    winners_pts = []
    losers_pts = []

    for t in trades:
        pts = t.get("profit_points", 0)
        cur = t.get("profit", 0)
        profits_pts.append(pts)
        profits_cur.append(cur)
        if pts > 0:
            winners_pts.append(pts)
        elif pts < 0:
            losers_pts.append(pts)

    wins = len(winners_pts)
    losses = len(losers_pts)
    total_profit_pts = sum(profits_pts)
    total_profit_currency = sum(profits_cur)
    max_profit_pts = max(profits_pts) if profits_pts else 0
    max_loss_pts = min(profits_pts) if profits_pts else 0
    avg_profit_pts = sum(winners_pts) / wins if wins > 0 else 0
    avg_loss_pts = sum(losers_pts) / losses if losses > 0 else 0
    win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0

    cumulative = []
    running = 0
    for p in profits_pts:
        running += p
        cumulative.append(round(running, 2))

    return {
        "total": total_trades,
        "wins": wins,
        "losses": losses,
        "total_profit_pts": total_profit_pts,
        "total_profit_currency": total_profit_currency,
        "max_profit_pts": max_profit_pts,
        "max_loss_pts": max_loss_pts,
        "avg_profit_pts": avg_profit_pts,
        "avg_loss_pts": avg_loss_pts,
        "win_rate": win_rate,
        "cumulative_pts": cumulative
    }

def format_datetime(dt_str):
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return dt_str

def generate_report():
    """Generate report.html from trades.json."""
    trades = load_trades(TRADES_FILE)
    stats = compute_stats(trades)
    total_trades = stats["total"]

    # Table rows
    table_rows = ""
    for idx, t in enumerate(trades, 1):
        ticket = t.get("ticket", "N/A")
        symbol = t.get("symbol", "N/A")
        direction = t.get("direction", "N/A").upper()
        open_time = format_datetime(t.get("open_time", ""))
        close_time = format_datetime(t.get("close_time", ""))
        open_price = t.get("open_price", 0)
        close_price = t.get("close_price", 0)
        profit_pts = t.get("profit_points", 0)
        profit_cur = t.get("profit", 0)
        close_reason = t.get("close_reason", "Unknown")
        final_sl = t.get("final_sl_points", "N/A")

        profit_class = "positive" if profit_pts > 0 else "negative" if profit_pts < 0 else "neutral"

        table_rows += f"""
        <tr>
            <td>{idx}</td>
            <td>{ticket}</td>
            <td>{symbol}</td>
            <td>{direction}</td>
            <td>{open_time}</td>
            <td>{close_time}</td>
            <td>{open_price:.2f}</td>
            <td>{close_price:.2f}</td>
            <td class="{profit_class}">{profit_pts:.1f}</td>
            <td class="{profit_class}">{profit_cur:.2f}</td>
            <td>{close_reason}</td>
            <td>{final_sl}</td>
        </tr>
        """

    cumulative = stats["cumulative_pts"]
    chart_labels = [f"Trade {i+1}" for i in range(len(cumulative))]

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trading Bot Execution Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{ box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
        body {{ background: #f5f7fa; margin: 20px; padding: 0; color: #1e293b; }}
        .container {{ max-width: 1400px; margin: 0 auto; background: white; padding: 25px 30px; border-radius: 16px; box-shadow: 0 8px 20px rgba(0,0,0,0.05); }}
        h1 {{ font-size: 2.2rem; font-weight: 600; margin-bottom: 0.2em; color: #0f172a; }}
        .subtitle {{ color: #64748b; font-size: 0.95rem; margin-bottom: 2em; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.8em; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 15px; margin-bottom: 30px; }}
        .stat-card {{ background: #f8fafc; border-radius: 12px; padding: 14px 16px; border-left: 4px solid #3b82f6; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }}
        .stat-card .label {{ font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.5px; color: #64748b; font-weight: 600; }}
        .stat-card .value {{ font-size: 1.6rem; font-weight: 700; margin-top: 4px; line-height: 1.2; }}
        .stat-card .value.positive {{ color: #22c55e; }}
        .stat-card .value.negative {{ color: #ef4444; }}
        .stat-card .value.neutral {{ color: #f59e0b; }}
        .chart-container {{ background: #fafcfd; border-radius: 12px; padding: 20px 15px 10px 15px; margin: 25px 0 30px 0; border: 1px solid #e9edf2; }}
        .chart-container h3 {{ margin-top: 0; margin-bottom: 10px; font-weight: 500; color: #1e293b; }}
        .table-container {{ overflow-x: auto; margin-top: 20px; border-radius: 12px; border: 1px solid #e9edf2; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; min-width: 800px; }}
        thead {{ background: #f1f5f9; border-bottom: 2px solid #d1d9e6; }}
        th {{ padding: 12px 10px; text-align: left; font-weight: 600; color: #334155; white-space: nowrap; }}
        td {{ padding: 10px 10px; border-bottom: 1px solid #e9edf2; }}
        tbody tr:nth-child(even) {{ background-color: #fafbfc; }}
        tbody tr:hover {{ background-color: #f0f4fe; }}
        .positive {{ color: #22c55e; font-weight: 600; }}
        .negative {{ color: #ef4444; font-weight: 600; }}
        .neutral {{ color: #f59e0b; }}
        .footer {{ margin-top: 30px; font-size: 0.8rem; color: #94a3b8; text-align: right; border-top: 1px solid #e2e8f0; padding-top: 15px; }}
        @media (max-width: 600px) {{ .container {{ padding: 15px; }} .stat-card .value {{ font-size: 1.2rem; }} }}
    </style>
</head>
<body>
<div class="container">
    <h1>📊 Trading Bot Execution Report</h1>
    <div class="subtitle">
        Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp; Total trades: {total_trades}
    </div>

    <div class="stats-grid">
        <div class="stat-card"><div class="label">Total Trades</div><div class="value">{stats["total"]}</div></div>
        <div class="stat-card"><div class="label">Wins / Losses</div><div class="value">{stats["wins"]} / {stats["losses"]}</div></div>
        <div class="stat-card"><div class="label">Win Rate</div><div class="value">{stats["win_rate"]:.1f}%</div></div>
        <div class="stat-card"><div class="label">Total Profit (pts)</div><div class="value {'positive' if stats['total_profit_pts'] > 0 else 'negative' if stats['total_profit_pts'] < 0 else 'neutral'}">{stats["total_profit_pts"]:.1f}</div></div>
        <div class="stat-card"><div class="label">Total Profit (currency)</div><div class="value {'positive' if stats['total_profit_currency'] > 0 else 'negative' if stats['total_profit_currency'] < 0 else 'neutral'}">{stats["total_profit_currency"]:.2f}</div></div>
        <div class="stat-card"><div class="label">Max Profit (pts)</div><div class="value positive">{stats["max_profit_pts"]:.1f}</div></div>
        <div class="stat-card"><div class="label">Max Loss (pts)</div><div class="value negative">{stats["max_loss_pts"]:.1f}</div></div>
        <div class="stat-card"><div class="label">Avg Win (pts)</div><div class="value positive">{stats["avg_profit_pts"]:.1f}</div></div>
        <div class="stat-card"><div class="label">Avg Loss (pts)</div><div class="value negative">{stats["avg_loss_pts"]:.1f}</div></div>
    </div>

    <div class="chart-container">
        <h3>📈 Cumulative Profit Over Trades</h3>
        <canvas id="profitChart" width="400" height="200"></canvas>
    </div>

    <h3 style="margin-top: 25px; margin-bottom: 10px;">📋 Trade Details</h3>
    <div class="table-container">
        <table>
            <thead><tr>
                <th>#</th><th>Ticket</th><th>Symbol</th><th>Direction</th>
                <th>Open Time</th><th>Close Time</th>
                <th>Open Price</th><th>Close Price</th>
                <th>Profit (pts)</th><th>Profit (cur)</th>
                <th>Close Reason</th><th>Final SL (pts)</th>
            </tr></thead>
            <tbody>{table_rows}</tbody>
        </table>
    </div>

    <div class="footer">Report generated automatically from trades.json • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
</div>

<script>
    (function() {{
        const ctx = document.getElementById('profitChart').getContext('2d');
        const labels = {json.dumps(chart_labels)};
        const dataPoints = {json.dumps(cumulative)};
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [{{
                    label: 'Cumulative Profit (points)',
                    data: dataPoints,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 2,
                    tension: 0.1,
                    fill: true,
                    pointRadius: 2,
                    pointBackgroundColor: '#3b82f6'
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: true,
                plugins: {{ legend: {{ display: true, position: 'top' }} }},
                scales: {{
                    y: {{ beginAtZero: true, title: {{ display: true, text: 'Profit (points)' }} }},
                    x: {{ title: {{ display: true, text: 'Trade Sequence' }} }}
                }}
            }}
        }});
    }})();
</script>

</body>
</html>
"""

    try:
        with open(REPORT_FILE, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"✅ HTML report generated: {REPORT_FILE}")
    except Exception as e:
        print(f"Error writing report: {e}")

# ======================================================
# TRADING BOT (UNCHANGED)
# ======================================================

def read_conclusion(file_path):
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None

def append_trade(trade_info, file_path=TRADES_FILE):
    try:
        try:
            with open(file_path, 'r') as f:
                trades = json.load(f)
                if not isinstance(trades, list):
                    trades = []
        except (FileNotFoundError, json.JSONDecodeError):
            trades = []
        trades.append(trade_info)
        with open(file_path, 'w') as f:
            json.dump(trades, f, indent=2)
        print(f"Trade logged to {file_path}")
    except Exception as e:
        print(f"Error writing to {file_path}: {e}")

def place_market_order(symbol, order_type, volume):
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"Symbol {symbol} not found.")
        return None
    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            print(f"Failed to select symbol {symbol}.")
            return None

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print(f"Failed to get tick for {symbol}.")
        return None

    if order_type == 'buy':
        price = tick.ask
        mt5_order_type = mt5.ORDER_TYPE_BUY
    else:
        price = tick.bid
        mt5_order_type = mt5.ORDER_TYPE_SELL

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": mt5_order_type,
        "price": price,
        "deviation": 20,
        "magic": 123456,
        "comment": "BotTrail",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result is None:
        print(f"Order_send returned None – last error: {mt5.last_error()}")
        return None

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Order failed: {result.comment}, retcode={result.retcode}")
        return None

    print(f"Order placed: {order_type.upper()} {volume} {symbol} at {price}")
    return {
        "ticket": result.order,
        "symbol": symbol,
        "direction": order_type,
        "volume": volume,
        "open_price": price,
        "open_time": datetime.now().isoformat(),
    }

def close_position(ticket, symbol, volume, direction):
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print(f"Failed to get tick for {symbol} during close.")
        return None

    if direction == 'buy':
        order_type = mt5.ORDER_TYPE_SELL
        price = tick.bid
    else:
        order_type = mt5.ORDER_TYPE_BUY
        price = tick.ask

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "position": ticket,
        "price": price,
        "deviation": 20,
        "magic": 123456,
        "comment": "CloseTrail",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result is None:
        print(f"Close order_send returned None – last error: {mt5.last_error()}")
        return None

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Close failed: {result.comment}, retcode={result.retcode}")
        return None

    print(f"Position {ticket} closed at {price}")
    return result

def monitor_and_close(trade, overall_start_time):
    symbol = trade["symbol"]
    ticket = trade["ticket"]
    direction = trade["direction"]
    open_price = trade["open_price"]
    volume = trade["volume"]

    point = mt5.symbol_info(symbol).point
    if point is None or point == 0:
        print(f"Invalid point value for {symbol}.")
        return trade

    sl_points = -SL_POINTS
    print(f"Initial stop-loss set at {sl_points} points")

    start_time = time.time()
    close_reason = None
    profit_points = 0
    last_print_time = 0

    while True:
        elapsed = time.time() - overall_start_time
        remaining = MAX_RUN_SECONDS - elapsed
        if remaining <= 0:
            print(f"\nGlobal runtime limit ({MAX_RUN_SECONDS}s) exceeded – closing position {ticket}.")
            close_reason = "global_timeout"
            close_result = close_position(ticket, symbol, volume, direction)
            break

        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            print(f"Position {ticket} no longer exists – assuming closed externally.")
            close_reason = "external_close"
            break

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            print("Failed to get tick, retrying...")
            time.sleep(CHECK_INTERVAL)
            continue

        if direction == 'buy':
            current_price = tick.bid
            profit_points = (current_price - open_price) / point
        else:
            current_price = tick.ask
            profit_points = (open_price - current_price) / point

        if profit_points >= 25:
            new_sl = 15 * max(0, (int(profit_points) - 25) // 25)
            if new_sl > sl_points:
                sl_points = new_sl
                print(f"Trailing SL updated to +{sl_points} pts")

        if time.time() - last_print_time >= 0.5:
            print(f"Profit: {profit_points:.2f} pts | SL: {sl_points} pts | Time left: {remaining:.1f}s", end='\r')
            last_print_time = time.time()

        if profit_points >= TP_POINTS:
            print(f"\nTP reached ({profit_points:.1f} pts) – closing position {ticket}")
            close_reason = "take_profit"
            close_result = close_position(ticket, symbol, volume, direction)
            break
        elif profit_points <= sl_points:
            print(f"\nSL hit (profit {profit_points:.1f} pts <= {sl_points} pts) – closing")
            close_reason = "stop_loss" if sl_points == -SL_POINTS else "trailing_stop"
            close_result = close_position(ticket, symbol, volume, direction)
            break

        if time.time() - start_time > MAX_WAIT_SECONDS:
            print(f"\nMax wait time exceeded – closing position {ticket} manually.")
            close_reason = "timeout"
            close_result = close_position(ticket, symbol, volume, direction)
            break

        time.sleep(CHECK_INTERVAL)

    if 'close_result' in locals() and close_result:
        close_price = close_result.price if hasattr(close_result, 'price') else current_price
        trade["close_price"] = close_price
        trade["close_time"] = datetime.now().isoformat()
        trade["profit_points"] = profit_points
        trade["profit"] = profit_points * point * volume * 100
    else:
        trade["close_time"] = datetime.now().isoformat()
        trade["profit_points"] = profit_points if 'profit_points' in locals() else None
        trade["note"] = f"Closed without explicit result (reason: {close_reason})"

    trade["close_reason"] = close_reason
    trade["final_sl_points"] = sl_points
    return trade

def main():
    if not mt5.initialize():
        print("MT5 initialization failed. Error:", mt5.last_error())
        return
    print("MT5 initialized.")

    conclusion = read_conclusion(CONCLUSION_FILE)
    if not conclusion:
        mt5.shutdown()
        return

    symbol = conclusion.get("symbol")
    if not symbol:
        print("No symbol in conclusion file.")
        mt5.shutdown()
        return

    conclusion_text = conclusion.get("conclusion", "").lower()
    timestamp = conclusion.get("timestamp", datetime.now().isoformat())

    if conclusion_text == "bullish":
        order_type = "buy"
    elif conclusion_text == "bearish":
        order_type = "sell"
    else:
        print("No actionable conclusion (neutral/unknown). Exiting.")
        mt5.shutdown()
        return

    overall_start = time.time()
    print(f"Starting bot for {symbol} – direction {order_type}")
    print(f"Will run for max {MAX_RUN_SECONDS} seconds (5 minutes) or until TP is hit.\n")

    try:
        while True:
            if time.time() - overall_start > MAX_RUN_SECONDS:
                print("Global runtime limit reached – no more trades.")
                break

            trade = place_market_order(symbol, order_type, VOLUME)
            if trade is None:
                print("Failed to place order. Exiting.")
                break

            trade = monitor_and_close(trade, overall_start)
            trade["conclusion"] = conclusion
            trade["timestamp"] = timestamp
            append_trade(trade)

            if trade.get("close_reason") == "take_profit":
                print("Take‑profit hit – stopping the bot.")
                break
            elif trade.get("close_reason") == "global_timeout":
                print("Global timeout triggered – bot stopped.")
                break
            elif trade.get("close_reason") in ["stop_loss", "trailing_stop", "timeout", "external_close"]:
                print(f"Trade closed by {trade.get('close_reason')} – re‑entering...")
                time.sleep(2)
                continue
            else:
                print(f"Unexpected close reason: {trade.get('close_reason')} – stopping.")
                break

    except KeyboardInterrupt:
        print("\n\n⚠️ Bot manually interrupted by user (Ctrl+C).")
        # Try to close any open position if we have a ticket? 
        # We'll just let it go – user can manually close.

    # --- Generate report (always) ---
    generate_report()

    mt5.shutdown()
    print("Bot finished.")

if __name__ == "__main__":
    main()