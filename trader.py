import json
import time
from datetime import datetime, timedelta
import MetaTrader5 as mt5

# --- Configuration ---
CONCLUSION_FILE = "conclusion.json"
TRADES_FILE = "trades.json"
VOLUME = 0.01
TP_POINTS = 250
INITIAL_SL_POINTS = 30
BREAK_EVEN_PROFIT = 15
TRAILING_STOP = 15
CHECK_INTERVAL = 1
TIMEOUT_SECONDS = 300
MAX_RETRIES = None
MIN_STOP_DISTANCE_POINTS = 20   # safety margin to avoid invalid stops

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

def get_valid_sl_price(symbol, direction, requested_sl, entry_price, min_points):
    """
    Ensure SL is valid: it must be at least min_points away from the current price
    and on the correct side of entry.
    """
    symbol_info = mt5.symbol_info(symbol)
    if not symbol_info:
        return None
    point = symbol_info.point
    tick = mt5.symbol_info_tick(symbol)
    
    if direction == 'buy':
        # SL must be below current bid and not too close
        min_sl = tick.bid - (min_points * point)
        # Also SL should not be above entry (for buy, SL should be below entry)
        if requested_sl >= entry_price:
            requested_sl = entry_price - (INITIAL_SL_POINTS * point)  # reset
        # Ensure at least min_points below bid
        if requested_sl > min_sl:
            requested_sl = min_sl
        # Finally, ensure SL is not above or equal to entry
        if requested_sl >= entry_price:
            requested_sl = entry_price - (INITIAL_SL_POINTS * point)
        return requested_sl
    else:  # sell
        # SL must be above current ask and not too close
        max_sl = tick.ask + (min_points * point)
        if requested_sl <= entry_price:
            requested_sl = entry_price + (INITIAL_SL_POINTS * point)
        if requested_sl < max_sl:
            requested_sl = max_sl
        if requested_sl <= entry_price:
            requested_sl = entry_price + (INITIAL_SL_POINTS * point)
        return requested_sl

def modify_sl(ticket, symbol, new_sl):
    """Modify stop-loss with validation."""
    position = mt5.positions_get(ticket=ticket)
    if not position or len(position) == 0:
        return False
    pos = position[0]
    direction = 'buy' if pos.type == mt5.ORDER_TYPE_BUY else 'sell'
    
    # Validate SL
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

    # Validate SL before sending
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
            # Check history to determine TP or SL
            from_date = datetime.now() - timedelta(minutes=5)
            deals = mt5.history_deals_get(ticket=ticket, from_date=from_date)
            if deals and len(deals) > 0:
                for deal in deals:
                    if deal.position_id == ticket and deal.type in (mt5.DEAL_TYPE_BUY, mt5.DEAL_TYPE_SELL):
                        close_price = deal.price
                        if direction == 'buy':
                            if close_price >= tp_price - 2 * point:
                                return 'tp'
                            else:
                                return 'sl'
                        else:
                            if close_price <= tp_price + 2 * point:
                                return 'tp'
                            else:
                                return 'sl'
            return 'sl'

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

        # Trailing logic with validation
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

        # Timeout
        if time.time() - start_time >= timeout_seconds:
            print(f"Timeout reached ({timeout_seconds}s). Closing position.")
            close_position(ticket, symbol)
            return 'timeout'

        time.sleep(CHECK_INTERVAL)

def run_trading_session(symbol, direction, volume, tp_points, initial_sl_points, timeout_seconds, max_retries):
    attempt = 0
    while True:
        if max_retries is not None and attempt >= max_retries:
            print(f"Max retries ({max_retries}) reached. Stopping.")
            break

        # Place order
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

        outcome = monitor_trade(ticket, symbol, entry_price, direction, point, tp_price, timeout_seconds)

        # Log outcome
        trade_record = {
            "symbol": symbol,
            "direction": direction,
            "volume": volume,
            "open_price": entry_price,
            "tp_price": tp_price,
            "initial_sl": result['sl_price'],
            "ticket": ticket,
            "outcome": outcome.upper(),
            "placed_at": datetime.now().isoformat(),
            "attempt": attempt + 1,
        }
        append_trade(trade_record)

        if outcome == 'tp':
            print(f"Trade {ticket} hit TP. Stopping trading session.")
            break

        elif outcome == 'sl':
            print(f"Trade {ticket} hit SL. Re-opening (attempt {attempt+1})")
            attempt += 1
            time.sleep(2)   # small delay before re-entering
            continue

        elif outcome == 'timeout':
            print(f"Trade {ticket} timed out and was closed. Stopping.")
            break

        else:
            break

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

    mt5.shutdown()
    print("Done.")

if __name__ == "__main__":
    main()