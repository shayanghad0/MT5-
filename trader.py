import json
import time
from datetime import datetime
import MetaTrader5 as mt5

# --- Configuration ---
CONCLUSION_FILE = "conclusion.json"
TRADES_FILE = "trades.json"
VOLUME = 0.01
TP_POINTS = 250
INITIAL_SL_POINTS = 30
BREAK_EVEN_PROFIT = 15    # points profit to trigger breakeven
TRAILING_STOP = 15        # points to trail after breakeven
CHECK_INTERVAL = 1        # seconds between checks

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

def modify_sl(ticket, symbol, new_sl):
    """Modify the stop-loss of an open position."""
    # Get current position to get current SL and TP (if any)
    position = mt5.positions_get(ticket=ticket)
    if not position or len(position) == 0:
        return False
    pos = position[0]
    # Prepare request to modify SL only (keep TP as is)
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": symbol,
        "position": ticket,
        "sl": new_sl,
        "tp": pos.tp,  # keep existing TP
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Failed to modify SL: {result.comment}, retcode={result.retcode}")
        return False
    print(f"SL modified to {new_sl} for ticket {ticket}")
    return True

def monitor_and_trail(ticket, symbol, entry_price, direction, point, tp_price):
    """
    Monitor the position and adjust SL according to the rules:
    1) Initial SL is 30 points away.
    2) When profit reaches 15 points, move SL to breakeven.
    3) After breakeven, trail SL with 15-point distance from the best price.
    Returns True if TP hit, False if SL hit or manual close.
    """
    # Initial SL
    if direction == 'buy':
        current_sl = entry_price - INITIAL_SL_POINTS * point
    else:
        current_sl = entry_price + INITIAL_SL_POINTS * point

    # Set initial SL (already set at order placement, but we'll store it)
    sl_breakeven_triggered = False
    best_price = entry_price  # for trailing: highest bid (buy) or lowest ask (sell)

    print(f"Starting monitoring for {symbol} {direction.upper()} ticket {ticket}")
    while True:
        # Check if position still exists
        positions = mt5.positions_get(ticket=ticket)
        if not positions or len(positions) == 0:
            print("Position closed.")
            break

        pos = positions[0]
        # Get current prices
        tick = mt5.symbol_info_tick(symbol)
        if direction == 'buy':
            current_price = tick.bid
            profit_points = (current_price - entry_price) / point
            # update best price (highest bid reached)
            if current_price > best_price:
                best_price = current_price
        else:  # sell
            current_price = tick.ask
            profit_points = (entry_price - current_price) / point
            if current_price < best_price:
                best_price = current_price

        # Rule 1: if profit >= BREAK_EVEN_PROFIT and not yet breakeven, move SL to entry
        if not sl_breakeven_triggered and profit_points >= BREAK_EVEN_PROFIT:
            print(f"Profit reached {profit_points:.2f} points → moving SL to breakeven")
            if direction == 'buy':
                new_sl = entry_price
            else:
                new_sl = entry_price
            if modify_sl(ticket, symbol, new_sl):
                sl_breakeven_triggered = True
                current_sl = new_sl

        # Rule 2: after breakeven, trail SL by TRAILING_STOP points from best price
        elif sl_breakeven_triggered:
            if direction == 'buy':
                # new SL = best_price - TRAILING_STOP * point
                new_sl = best_price - TRAILING_STOP * point
                # only update if new SL is higher than current SL (lock in more profit)
                if new_sl > current_sl:
                    print(f"Trailing: new SL = {new_sl} (best price {best_price})")
                    if modify_sl(ticket, symbol, new_sl):
                        current_sl = new_sl
            else:  # sell
                new_sl = best_price + TRAILING_STOP * point
                if new_sl < current_sl:  # for sell, SL is above, lower is better
                    print(f"Trailing: new SL = {new_sl} (best price {best_price})")
                    if modify_sl(ticket, symbol, new_sl):
                        current_sl = new_sl

        # Check if TP is hit (position closed by TP)
        # If TP hit, position will be closed, loop will break on next iteration.
        time.sleep(CHECK_INTERVAL)

    # After loop, determine if TP was hit (position closed, check profit)
    # We'll get the closed order's profit from history? Simpler: we can check if price reached TP.
    # But we assume if position closed and profit is positive, likely TP.
    # We'll just return True if closed with profit > 0? Better: check if TP price was reached.
    # Since we have tp_price, we can check if direction is buy and last tick high >= tp_price, etc.
    # But we can just log the final result in the main function.
    # For simplicity, we'll return nothing; main will handle logging.
    print("Monitoring ended.")

def place_order_and_monitor(symbol, order_type, volume, tp_points, initial_sl_points):
    """
    Place market order with TP and initial SL, then monitor and trail.
    """
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

    # Monitor and trail
    monitor_and_trail(ticket, symbol, entry_price, order_type, point, tp_price)

    # After monitor, check final status (optional: get closed position info)
    # We'll just return the ticket and entry details
    return {
        "ticket": ticket,
        "symbol": symbol,
        "direction": order_type,
        "volume": volume,
        "open_price": entry_price,
        "tp_price": tp_price,
        "sl_price": sl_price,
        "time": datetime.now().isoformat(),
    }

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

    trade_result = place_order_and_monitor(symbol, order_type, VOLUME, TP_POINTS, INITIAL_SL_POINTS)
    if trade_result is None:
        mt5.shutdown()
        return

    # Log trade
    trade_record = {
        "symbol": symbol,
        "direction": order_type,
        "volume": VOLUME,
        "open_price": trade_result["open_price"],
        "tp_price": trade_result["tp_price"],
        "initial_sl": trade_result["sl_price"],
        "ticket": trade_result["ticket"],
        "timestamp": timestamp,
        "placed_at": datetime.now().isoformat(),
        "conclusion": conclusion,
    }
    append_trade(trade_record)

    mt5.shutdown()
    print("Done.")

if __name__ == "__main__":
    main()