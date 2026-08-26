import json
import time
from datetime import datetime
import MetaTrader5 as mt5

# --- Configuration ---
CONCLUSION_FILE = "conclusion.json"
TRADES_FILE = "trades.json"
VOLUME = 0.01                 # Fixed lot size (adjust as needed)
TP_POINTS = 250               # Take Profit in points (symbol-specific)

def read_conclusion(file_path):
    """Read and parse the conclusion JSON file."""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None

def append_trade(trade_info, file_path=TRADES_FILE):
    """Append a trade record to the trades JSON file."""
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

def place_market_order(symbol, order_type, volume, tp_points):
    """
    Place a market order (buy or sell) with a Take Profit set to tp_points
    from the entry price. No Stop Loss.
    Returns the order result dictionary or None if failed.
    """
    # Ensure symbol is available
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

    # Determine entry price and TP price
    if order_type == 'buy':
        entry_price = tick.ask
        tp_price = entry_price + (tp_points * point)
    else:  # sell
        entry_price = tick.bid
        tp_price = entry_price - (tp_points * point)

    # Prepare the order request
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_BUY if order_type == 'buy' else mt5.ORDER_TYPE_SELL,
        "price": entry_price,
        "tp": tp_price,               # <--- TAKE PROFIT SET HERE
        "deviation": 20,
        "magic": 123456,
        "comment": "Bot trade",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    # Send the order
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Order failed: {result.comment}, retcode={result.retcode}")
        return None

    print(f"Order placed: {order_type.upper()} {volume} {symbol} at {entry_price}, TP at {tp_price}")
    return {
        "ticket": result.order,
        "symbol": symbol,
        "direction": order_type,
        "volume": volume,
        "open_price": entry_price,
        "tp_price": tp_price,
        "time": datetime.now().isoformat(),
        "comment": result.comment,
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

    print(f"Received conclusion for {symbol}: {conclusion_text}")

    if conclusion_text == "bullish":
        order_type = "buy"
    elif conclusion_text == "bearish":
        order_type = "sell"
    else:
        print("No actionable conclusion (neutral or unknown). Exiting.")
        return

    trade_result = place_market_order(symbol, order_type, VOLUME, TP_POINTS)
    if trade_result is None:
        return

    trade_record = {
        "symbol": symbol,
        "direction": order_type,
        "volume": VOLUME,
        "open_price": trade_result["open_price"],
        "tp_price": trade_result["tp_price"],
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