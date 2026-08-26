import json
import time
from datetime import datetime, timedelta
import MetaTrader5 as mt5
import os

# --- Configuration ---
CONCLUSION_FILE = "conclusion.json"
TRADES_FILE = "trades.json"
REPORT_FILE = "report.html"
VOLUME = 0.01
TP_POINTS = 250
INITIAL_SL_POINTS = 30
BREAK_EVEN_PROFIT = 15
TRAILING_STOP = 15
CHECK_INTERVAL = 1
TIMEOUT_SECONDS = 300
MAX_RETRIES = None
MIN_STOP_DISTANCE_POINTS = 20

# ---------- Helper functions ----------

def read_conclusion(file_path):
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None

def load_trades(file_path=TRADES_FILE):
    try:
        with open(file_path, 'r') as f:
            trades = json.load(f)
            return trades if isinstance(trades, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def append_trade(trade_info, file_path=TRADES_FILE):
    trades = load_trades(file_path)
    trades.append(trade_info)
    with open(file_path, 'w') as f:
        json.dump(trades, f, indent=2)
    print(f"Trade logged to {file_path}")

def get_valid_sl_price(symbol, direction, requested_sl, entry_price, min_points):
    symbol_info = mt5.symbol_info(symbol)
    if not symbol_info:
        return None
    point = symbol_info.point
    tick = mt5.symbol_info_tick(symbol)

    if direction == 'buy':
        min_sl = tick.bid - (min_points * point)
        if requested_sl >= entry_price:
            requested_sl = entry_price - (INITIAL_SL_POINTS * point)
        if requested_sl > min_sl:
            requested_sl = min_sl
        if requested_sl >= entry_price:
            requested_sl = entry_price - (INITIAL_SL_POINTS * point)
        return requested_sl
    else:  # sell
        max_sl = tick.ask + (min_points * point)
        if requested_sl <= entry_price:
            requested_sl = entry_price + (INITIAL_SL_POINTS * point)
        if requested_sl < max_sl:
            requested_sl = max_sl
        if requested_sl <= entry_price:
            requested_sl = entry_price + (INITIAL_SL_POINTS * point)
        return requested_sl

def modify_sl(ticket, symbol, new_sl):
    position = mt5.positions_get(ticket=ticket)
    if not position or len(position) == 0:
        return False
    pos = position[0]
    direction = 'buy' if pos.type == mt5.ORDER_TYPE_BUY else 'sell'
    valid_sl = get_valid_sl_price(symbol, direction, new_sl, pos.price_open, MIN_STOP_DISTANCE_POINTS)
    if valid_sl is None or abs(valid_sl - new_sl) > 0.0001:
        print(f"SL {new_sl} invalid, using {valid_sl} instead")
        new_sl = valid_sl

    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": symbol,
        "position": ticket,
        "sl": new_sl,
        "tp": pos.tp,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Failed to modify SL: {result.comment}, retcode={result.retcode}")
        return False
    print(f"SL modified to {new_sl} for ticket {ticket}")
    return True

def close_position(ticket, symbol):
    position = mt5.positions_get(ticket=ticket)
    if not position or len(position) == 0:
        return True
    pos = position[0]
    order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    tick = mt5.symbol_info_tick(symbol)
    price = tick.bid if order_type == mt5.ORDER_TYPE_SELL else tick.ask
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": pos.volume,
        "type": order_type,
        "position": ticket,
        "price": price,
        "deviation": 20,
        "magic": 123456,
        "comment": "close by timeout",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Failed to close position: {result.comment}, retcode={result.retcode}")
        return False
    print(f"Position closed manually (timeout).")
    return True

def get_close_info(ticket):
    """Retrieve close price and profit from history for a given ticket."""
    # Get all deals for this position (last 10 minutes)
    from_date = datetime.now() - timedelta(minutes=10)
    deals = mt5.history_deals_get(position=ticket, from_date=from_date)
    if deals and len(deals) > 0:
        # The closing deal is usually the last one that is not a reversal
        for deal in reversed(deals):
            if deal.type in (mt5.DEAL_TYPE_BUY, mt5.DEAL_TYPE_SELL):
                return {
                    "close_price": deal.price,
                    "profit": deal.profit,
                    "profit_currency": deal.profit_currency,
                    "time": deal.time,
                }
    return None

def place_order(symbol, order_type, volume, tp_points, initial_sl_points):
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"Symbol {symbol} not found.")
        return None
    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            print(f"Failed to select symbol {symbol}.")
            return None

    tick = mt5.symbol_info_tick(symbol)
    point = symbol_info.point

    if order_type == 'buy':
        entry_price = tick.ask
        tp_price = entry_price + tp_points * point
        sl_price = entry_price - initial_sl_points * point
    else:
        entry_price = tick.bid
        tp_price = entry_price - tp_points * point
        sl_price = entry_price + initial_sl_points * point

    valid_sl = get_valid_sl_price(symbol, order_type, sl_price, entry_price, MIN_STOP_DISTANCE_POINTS)
    if valid_sl is None:
        print("Could not calculate valid SL, skipping order.")
        return None
    sl_price = valid_sl

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_BUY if order_type == 'buy' else mt5.ORDER_TYPE_SELL,
        "price": entry_price,
        "tp": tp_price,
        "sl": sl_price,
        "deviation": 20,
        "magic": 123456,
        "comment": "Bot trade with trailing SL",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Order failed: {result.comment}, retcode={result.retcode}")
        return None

    ticket = result.order
    print(f"Order placed: {order_type.upper()} {volume} {symbol} at {entry_price}, TP {tp_price}, SL {sl_price}")
    return {
        "ticket": ticket,
        "entry_price": entry_price,
        "tp_price": tp_price,
        "sl_price": sl_price,
        "point": point,
    }

def monitor_trade(ticket, symbol, entry_price, direction, point, tp_price, timeout_seconds):
    start_time = time.time()
    sl_breakeven_triggered = False
    best_price = entry_price
    current_sl = entry_price - INITIAL_SL_POINTS * point if direction == 'buy' else entry_price + INITIAL_SL_POINTS * point

    while True:
        positions = mt5.positions_get(ticket=ticket)
        if not positions or len(positions) == 0:
            # Position closed – get close info
            close_info = get_close_info(ticket)
            if close_info:
                # Determine outcome based on close price relative to TP
                if direction == 'buy':
                    if close_info['close_price'] >= tp_price - 2 * point:
                        outcome = 'tp'
                    else:
                        outcome = 'sl'
                else:
                    if close_info['close_price'] <= tp_price + 2 * point:
                        outcome = 'tp'
                    else:
                        outcome = 'sl'
                return outcome, close_info
            else:
                return 'sl', None  # fallback

        pos = positions[0]
        tick = mt5.symbol_info_tick(symbol)

        if direction == 'buy':
            current_price = tick.bid
            profit_points = (current_price - entry_price) / point
            if current_price > best_price:
                best_price = current_price
        else:
            current_price = tick.ask
            profit_points = (entry_price - current_price) / point
            if current_price < best_price:
                best_price = current_price

        if not sl_breakeven_triggered and profit_points >= BREAK_EVEN_PROFIT:
            print(f"Profit reached {profit_points:.2f} points → moving SL to breakeven")
            new_sl = entry_price
            if modify_sl(ticket, symbol, new_sl):
                sl_breakeven_triggered = True
                current_sl = new_sl
        elif sl_breakeven_triggered:
            if direction == 'buy':
                new_sl = best_price - TRAILING_STOP * point
                if new_sl > current_sl:
                    print(f"Trailing: new SL = {new_sl} (best price {best_price})")
                    if modify_sl(ticket, symbol, new_sl):
                        current_sl = new_sl
            else:
                new_sl = best_price + TRAILING_STOP * point
                if new_sl < current_sl:
                    print(f"Trailing: new SL = {new_sl} (best price {best_price})")
                    if modify_sl(ticket, symbol, new_sl):
                        current_sl = new_sl

        if time.time() - start_time >= timeout_seconds:
            print(f"Timeout reached ({timeout_seconds}s). Closing position.")
            close_position(ticket, symbol)
            # Wait a bit for history to update
            time.sleep(1)
            close_info = get_close_info(ticket)
            return 'timeout', close_info

        time.sleep(CHECK_INTERVAL)

def run_trading_session(symbol, direction, volume, tp_points, initial_sl_points, timeout_seconds, max_retries):
    attempt = 0
    while True:
        if max_retries is not None and attempt >= max_retries:
            print(f"Max retries ({max_retries}) reached. Stopping.")
            break

        result = place_order(symbol, direction, volume, tp_points, initial_sl_points)
        if not result:
            print("Order placement failed, retrying after delay...")
            time.sleep(5)
            attempt += 1
            continue

        ticket = result['ticket']
        entry_price = result['entry_price']
        tp_price = result['tp_price']
        point = result['point']

        outcome, close_info = monitor_trade(ticket, symbol, entry_price, direction, point, tp_price, timeout_seconds)

        # Build trade record
        trade_record = {
            "symbol": symbol,
            "direction": direction,
            "volume": volume,
            "open_price": entry_price,
            "tp_price": tp_price,
            "initial_sl": result['sl_price'],
            "ticket": ticket,
            "outcome": outcome.upper(),
            "attempt": attempt + 1,
            "open_time": datetime.now().isoformat(),
        }
        if close_info:
            trade_record.update({
                "close_price": close_info['close_price'],
                "profit": close_info['profit'],
                "profit_currency": close_info['profit_currency'],
                "close_time": datetime.fromtimestamp(close_info['time']).isoformat()
            })
        else:
            trade_record.update({
                "close_price": None,
                "profit": None,
                "profit_currency": None,
                "close_time": None
            })

        append_trade(trade_record)

        if outcome == 'tp':
            print(f"Trade {ticket} hit TP. Stopping trading session.")
            break
        elif outcome == 'sl':
            print(f"Trade {ticket} hit SL. Re-opening (attempt {attempt+1})")
            attempt += 1
            time.sleep(2)
            continue
        elif outcome == 'timeout':
            print(f"Trade {ticket} timed out and was closed. Stopping.")
            break
        else:
            break

# ---------- HTML Report Generator ----------

def generate_html_report(trades_file=TRADES_FILE, output_file=REPORT_FILE):
    trades = load_trades(trades_file)
    if not trades:
        print("No trades found to generate report.")
        return

    # Compute stats
    total_trades = len(trades)
    wins = [t for t in trades if t.get('profit', 0) > 0]
    losses = [t for t in trades if t.get('profit', 0) < 0]
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = win_count / total_trades * 100 if total_trades > 0 else 0
    total_profit = sum(t.get('profit', 0) for t in trades)
    avg_profit = total_profit / total_trades if total_trades > 0 else 0
    max_profit = max((t.get('profit', 0) for t in trades), default=0)
    max_loss = min((t.get('profit', 0) for t in trades), default=0)
    # Best and worst trades
    best_trade = max(trades, key=lambda x: x.get('profit', 0)) if trades else None
    worst_trade = min(trades, key=lambda x: x.get('profit', 0)) if trades else None

    # Build HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Trading Bot Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #f4f6f9; }}
            .container {{ max-width: 1200px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
            .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px,1fr)); gap: 15px; margin: 20px 0; }}
            .stat-box {{ background: #ecf0f1; padding: 15px; border-radius: 6px; text-align: center; }}
            .stat-box .label {{ font-size: 14px; color: #7f8c8d; }}
            .stat-box .value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
            .stat-box.profit .value {{ color: #27ae60; }}
            .stat-box.loss .value {{ color: #e74c3c; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ padding: 10px; text-align: center; border-bottom: 1px solid #ddd; }}
            th {{ background: #34495e; color: white; }}
            tr.win {{ background: #d5f5e3; }}
            tr.loss {{ background: #fadbd8; }}
            tr.timeout {{ background: #fcf3cf; }}
            .footer {{ margin-top: 20px; color: #95a5a6; font-size: 12px; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📊 Trading Bot Performance Report</h1>
            <div class="stats">
                <div class="stat-box"><span class="label">Total Trades</span><div class="value">{total_trades}</div></div>
                <div class="stat-box"><span class="label">Win Rate</span><div class="value">{win_rate:.1f}%</div></div>
                <div class="stat-box profit"><span class="label">Total P&L</span><div class="value">{total_profit:.2f}</div></div>
                <div class="stat-box"><span class="label">Avg P&L</span><div class="value">{avg_profit:.2f}</div></div>
                <div class="stat-box profit"><span class="label">Best Trade</span><div class="value">{max_profit:.2f}</div></div>
                <div class="stat-box loss"><span class="label">Worst Trade</span><div class="value">{max_loss:.2f}</div></div>
            </div>
            <h2>Trade History</h2>
            <table>
                <tr>
                    <th>Ticket</th>
                    <th>Symbol</th>
                    <th>Direction</th>
                    <th>Volume</th>
                    <th>Open Price</th>
                    <th>Close Price</th>
                    <th>Profit</th>
                    <th>Outcome</th>
                    <th>Open Time</th>
                    <th>Close Time</th>
                </tr>
    """

    for t in trades:
        direction = t.get('direction', '').upper()
        outcome = t.get('outcome', '')
        profit = t.get('profit', 0)
        row_class = 'win' if profit > 0 else 'loss' if profit < 0 else 'timeout'
        close_price = t.get('close_price', '')
        if close_price is None:
            close_price = '-'
        open_time = t.get('open_time', '')[:19] if t.get('open_time') else ''
        close_time = t.get('close_time', '')[:19] if t.get('close_time') else ''
        html += f"""
                <tr class="{row_class}">
                    <td>{t.get('ticket', '')}</td>
                    <td>{t.get('symbol', '')}</td>
                    <td>{direction}</td>
                    <td>{t.get('volume', '')}</td>
                    <td>{t.get('open_price', '')}</td>
                    <td>{close_price}</td>
                    <td>{profit:.2f if profit is not None else '-'}</td>
                    <td>{outcome}</td>
                    <td>{open_time}</td>
                    <td>{close_time}</td>
                </tr>
        """

    html += """
            </table>
            <div class="footer">
                Report generated on {0} by MT5 Trader Bot.
            </div>
        </div>
    </body>
    </html>
    """.format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    with open(output_file, 'w') as f:
        f.write(html)
    print(f"HTML report saved to {output_file}")

# ---------- Main ----------

def main():
    if not mt5.initialize():
        print("MT5 initialization failed.")
        return
    print("MT5 initialized.")

    conclusion = read_conclusion(CONCLUSION_FILE)
    if not conclusion:
        mt5.shutdown()
        return

    symbol = conclusion.get("symbol")
    conclusion_text = conclusion.get("conclusion", "").lower()
    timestamp = conclusion.get("timestamp", datetime.now().isoformat())

    if conclusion_text == "bullish":
        direction = "buy"
    elif conclusion_text == "bearish":
        direction = "sell"
    else:
        print("No actionable conclusion. Exiting.")
        mt5.shutdown()
        return

    print(f"Starting trading session for {symbol} {direction.upper()}")
    run_trading_session(
        symbol=symbol,
        direction=direction,
        volume=VOLUME,
        tp_points=TP_POINTS,
        initial_sl_points=INITIAL_SL_POINTS,
        timeout_seconds=TIMEOUT_SECONDS,
        max_retries=MAX_RETRIES
    )

    # Generate HTML report from saved trades
    generate_html_report()

    mt5.shutdown()
    print("Done. Report generated.")

if __name__ == "__main__":
    main()