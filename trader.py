import json
import time
from datetime import datetime
import MetaTrader5 as mt5

# --- Configuration ---
CONCLUSION_FILE = "conclusion.json"
TRADES_FILE = "trades.json"
VOLUME = 0.01  # Fixed lot size (adjust as needed)

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
        # Load existing trades or create an empty list
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
    """
    Place a market order (buy or sell) with no SL/TP.
    order_type: 'buy' or 'sell'
    Returns the order result dictionary or None if failed.
    """
    # Ensure symbol is available
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"Symbol {symbol} not found.")
        return None

    # If the symbol is not visible, add it
    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            print(f"Failed to select symbol {symbol}.")
            return None

    # Prepare the order request
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_BUY if order_type == 'buy' else mt5.ORDER_TYPE_SELL,
        "price": mt5.symbol_info_tick(symbol).ask if order_type == 'buy' else mt5.symbol_info_tick(symbol).bid,
        "deviation": 20,  # Slippage tolerance in points
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

    print(f"Order placed: {order_type.upper()} {volume} {symbol} at {request['price']}")
    return {
        "ticket": result.order,
        "symbol": symbol,
        "direction": order_type,
        "volume": volume,
        "open_price": request["price"],
        "time": datetime.now().isoformat(),
        "comment": result.comment,
    }

def main():
    # Initialize MT5 connection
    if not mt5.initialize():
        print("MT5 initialization failed.")
        return

    print("MT5 initialized. Terminal info:", mt5.terminal_info())

    # Read the conclusion
    conclusion = read_conclusion(CONCLUSION_FILE)
    if not conclusion:
        return

    symbol = conclusion.get("symbol")
    conclusion_text = conclusion.get("conclusion", "").lower()
    timestamp = conclusion.get("timestamp", datetime.now().isoformat())

    print(f"Received conclusion for {symbol}: {conclusion_text}")

    # Determine action
    if conclusion_text == "bullish":
        order_type = "buy"
    elif conclusion_text == "bearish":
        order_type = "sell"
    else:
        print("No actionable conclusion (neutral or unknown). Exiting.")
        return

    # Place the order
    trade_result = place_market_order(symbol, order_type, VOLUME)
    if trade_result is None:
        return

    # Append trade info to trades.json (including the conclusion data)
    trade_record = {
        "symbol": symbol,
        "direction": order_type,
        "volume": VOLUME,
        "open_price": trade_result["open_price"],
        "ticket": trade_result["ticket"],
        "timestamp": timestamp,
        "placed_at": datetime.now().isoformat(),
        "conclusion": conclusion,  # keep the full original conclusion for reference
    }
    append_trade(trade_record)

    # Shutdown MT5
    mt5.shutdown()
    print("Done.")

if __name__ == "__main__":
    main()