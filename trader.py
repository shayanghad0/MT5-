import json
import time
from datetime import datetime
import MetaTrader5 as mt5

# --- Configuration ---
CONCLUSION_FILE = "conclusion.json"
TRADES_FILE = "trades.json"
VOLUME = 0.01                     # Fixed lot size
TP_POINTS = 50                   # Target profit in points (not pips)
CHECK_INTERVAL = 1                # Seconds between price checks
MAX_WAIT_SECONDS = 3600 * 24      # Stop monitoring after 24h (optional)

def read_conclusion(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)

def append_trade(trade_info, file_path=TRADES_FILE):
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
        "comment": "Bot trade - virtual TP",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
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
    """Close a position by ticket using opposite market order."""
    # Determine opposite direction
    if direction == 'buy':
        order_type = mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(symbol).bid
    else:
        order_type = mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(symbol).ask

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "position": ticket,
        "price": price,
        "deviation": 20,
        "magic": 123456,
        "comment": "Close via virtual TP",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Close failed: {result.comment}, retcode={result.retcode}")
        return None
    print(f"Position {ticket} closed at {price}")
    return result

def monitor_and_close(trade):
    """Monitor price until TP is hit, then close the trade."""
    symbol = trade["symbol"]
    ticket = trade["ticket"]
    direction = trade["direction"]
    open_price = trade["open_price"]
    volume = trade["volume"]

    # Get point value
    point = mt5.symbol_info(symbol).point
    tp_in_price = TP_POINTS * point   # absolute price difference

    start_time = time.time()
    while True:
        # Check if position still exists (in case it was closed manually)
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            print(f"Position {ticket} no longer exists – assuming closed.")
            break

        # Get current price
        tick = mt5.symbol_info_tick(symbol)
        if direction == 'buy':
            current_price = tick.bid   # for profit calculation, buy uses bid
            profit_points = (current_price - open_price) / point
        else:
            current_price = tick.ask   # sell uses ask
            profit_points = (open_price - current_price) / point

        print(f"Current profit: {profit_points:.1f} points", end='\r')

        # Check if TP reached
        if profit_points >= TP_POINTS:
            print(f"\nTP reached ({profit_points:.1f} pts) – closing position {ticket}")
            close_result = close_position(ticket, symbol, volume, direction)
            if close_result:
                # Update trade record with close info
                close_price = close_result.price if hasattr(close_result, 'price') else current_price
                trade["close_price"] = close_price
                trade["close_time"] = datetime.now().isoformat()
                trade["profit_points"] = profit_points
                trade["profit"] = (close_price - open_price) * volume * 100 if direction == 'buy' else (open_price - close_price) * volume * 100
                # approximate profit in deposit currency (simplified)
                # For XAUUSD, 1 point = 0.01, volume 0.01 -> profit = points * 0.01 * 100? Actually, we'll just store points.
                # More accurate: trade["profit"] = profit_points * point * volume * 100? Let's just store points and let user calculate.
                trade["profit"] = profit_points * point * volume * 100  # simplified, check symbol trade calculation
            else:
                trade["close_time"] = datetime.now().isoformat()
                trade["note"] = "Close attempt failed"
            break

        # Optional timeout
        if time.time() - start_time > MAX_WAIT_SECONDS:
            print(f"\nMax wait time exceeded – closing position {ticket} manually.")
            close_position(ticket, symbol, volume, direction)
            trade["close_time"] = datetime.now().isoformat()
            trade["note"] = "Closed due to timeout"
            break

        time.sleep(CHECK_INTERVAL)

    return trade

def main():
    if not mt5.initialize():
        print("MT5 initialization failed.")
        return
    print("MT5 initialized.")

    conclusion = read_conclusion(CONCLUSION_FILE)
    if not conclusion:
        return

    symbol = conclusion.get("symbol")
    conclusion_text = conclusion.get("conclusion", "").lower()
    timestamp = conclusion.get("timestamp", datetime.now().isoformat())

    if conclusion_text == "bullish":
        order_type = "buy"
    elif conclusion_text == "bearish":
        order_type = "sell"
    else:
        print("No actionable conclusion. Exiting.")
        mt5.shutdown()
        return

    # Place the order
    trade = place_market_order(symbol, order_type, VOLUME)
    if trade is None:
        mt5.shutdown()
        return

    # Monitor until TP or timeout
    trade = monitor_and_close(trade)

    # Add conclusion data
    trade["conclusion"] = conclusion
    trade["timestamp"] = timestamp

    # Log final trade record
    append_trade(trade)

    mt5.shutdown()
    print("Done.")

if __name__ == "__main__":
    main()