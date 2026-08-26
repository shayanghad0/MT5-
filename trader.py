import json
import time
from datetime import datetime
import MetaTrader5 as mt5

# --- Configuration ---
CONCLUSION_FILE = "conclusion.json"
TRADES_FILE = "trades.json"
VOLUME = 0.01                     # Fixed lot size
TP_POINTS = 250                   # Take-profit in points
CHECK_INTERVAL = 1                # Seconds between price checks
MAX_WAIT_SECONDS = 3600 * 24      # Stop monitoring after 24h (optional)

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
        "comment": "BotTrail",                      # <31 chars
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,      # Most widely supported
    }

    result = mt5.order_send(request)
    if result is None:
        print(f"Order_send returned None – last error: {mt5.last_error()}")
        return None

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Order failed: {result.comment}, retcode={result.retcode}")
        # Optionally retry with FOK if IOC fails
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

def monitor_and_close(trade):
    symbol = trade["symbol"]
    ticket = trade["ticket"]
    direction = trade["direction"]
    open_price = trade["open_price"]
    volume = trade["volume"]

    point = mt5.symbol_info(symbol).point
    if point is None or point == 0:
        print(f"Invalid point value for {symbol}.")
        return trade

    start_time = time.time()
    close_reason = None
    sl_points = None
    profit_points = 0

    while True:
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

        # Update trailing stop
        if profit_points >= 25:
            new_sl = 15 * max(0, (int(profit_points) - 25) // 25)
            if sl_points is None or new_sl > sl_points:
                sl_points = new_sl
                print(f"Trailing SL updated to +{sl_points} pts")

        # TP / SL checks
        if profit_points >= TP_POINTS:
            print(f"\nTP reached ({profit_points:.1f} pts) – closing position {ticket}")
            close_reason = "take_profit"
            close_result = close_position(ticket, symbol, volume, direction)
            break
        elif sl_points is not None and profit_points <= sl_points:
            print(f"\nTrailing SL hit (profit {profit_points:.1f} pts <= {sl_points} pts) – closing")
            close_reason = "trailing_stop"
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

    trade = place_market_order(symbol, order_type, VOLUME)
    if trade is None:
        print("Failed to place order. Exiting.")
        mt5.shutdown()
        return

    trade = monitor_and_close(trade)
    trade["conclusion"] = conclusion
    trade["timestamp"] = timestamp

    append_trade(trade)
    mt5.shutdown()
    print("Done.")

if __name__ == "__main__":
    main()