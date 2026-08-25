"""
Export the last 30 completed 1‑minute candles for a chosen symbol from MT5 to a JSON file.
Each candle is stored with UTC time (the timezone used by MT5) and OHLCV.

Example output:
{
    "date": "2026-08-25",
    "clock": "14:23:45",
    "timezone": "+00:00",
    "open": 1234.56,
    "high": 1234.78,
    "low": 1234.12,
    "close": 1234.34,
    "volume": 156
}

Usage:
    python export_candles.py [SYMBOL]
If no symbol is provided, the script prompts for one.
The output file is named '<SYMBOL>_1m_30candles.json'.
"""

import sys
import json
from datetime import datetime, timezone
import MetaTrader5 as mt5

# --- Configuration ---
TIMEFRAME = mt5.TIMEFRAME_M1   # 1-minute
CANDLE_COUNT = 30              # number of completed bars to fetch

def get_candles(symbol: str) -> list:
    """
    Fetch the last CANDLE_COUNT completed 1‑minute OHLCV bars from MT5.
    Returns a list of dictionaries with date, clock, timezone (UTC), OHLCV.
    """
    if not mt5.initialize():
        raise RuntimeError("MT5 initialization failed. Make sure MetaTrader 5 is running.")

    # Add the symbol to Market Watch (if available)
    if not mt5.symbol_select(symbol, True):
        mt5.shutdown()
        raise ValueError(f"Symbol '{symbol}' not found on the server. Please check the name.")

    # Get CANDLE_COUNT bars, skipping the current incomplete bar (start=1)
    rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME, 1, CANDLE_COUNT)

    if rates is None:
        mt5.shutdown()
        raise RuntimeError(f"Failed to retrieve candle data for {symbol}. "
                           f"Error: {mt5.last_error()}")

    # Convert each rate – timestamps are already UTC
    candles = []
    for rate in rates:
        dt_utc = datetime.fromtimestamp(rate[0], tz=timezone.utc)

        candles.append({
            "date": dt_utc.strftime("%Y-%m-%d"),
            "clock": dt_utc.strftime("%H:%M:%S"),
            "timezone": "+00:00",          # MT5 uses UTC internally
            "open": float(rate[1]),
            "high": float(rate[2]),
            "low": float(rate[3]),
            "close": float(rate[4]),
            "volume": int(rate[5])
        })

    mt5.shutdown()
    return candles

def save_to_json(candles: list, symbol: str) -> None:
    """Save the candles list to a JSON file."""
    filename = "candles.json"
    with open(filename, "w") as f:
        json.dump(candles, f, indent=2)
    print(f"Saved {len(candles)} candles to '{filename}'")

def main():
    if len(sys.argv) > 1:
        symbol = sys.argv[1].upper()
    else:
        symbol = input("Enter symbol (e.g., XAUUSD, EURUSD, XAGUSD): ").strip().upper()

    try:
        candles = get_candles(symbol)
        save_to_json(candles, symbol)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()