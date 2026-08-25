import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone

def predict_next_5_candles_fib(df, lookback=30, sma_period=20):
    """
    Predict direction for the next 5 candles based on Fibonacci Retracement Levels.
    Uses:
      - Swing high = max(high) over last `lookback` candles
      - Swing low = min(low) over last `lookback` candles
      - Levels: 0.0 (low), 0.236, 0.382, 0.5, 0.618, 0.786, 1.0 (high)
      - Price above 0.5 -> bullish; below -> bearish
      - If near key support/resistance levels (0.236 or 0.786), confidence increases
      - SMA(20) trend filter for tie‑breaking when price is near 0.5
    Always returns bullish or bearish (no neutral).
    """
    if len(df) < max(lookback, sma_period):
        raise ValueError(f"Need at least {max(lookback, sma_period)} candles.")

    # ---- Fibonacci Levels from last `lookback` candles ----
    recent_df = df.tail(lookback)
    swing_high = recent_df['high'].max()
    swing_low = recent_df['low'].min()
    diff = swing_high - swing_low

    if diff == 0:
        # If price range is zero, fall back to SMA trend
        diff = 1e-9  # avoid division by zero

    levels = {
        '0.0': swing_low,
        '0.236': swing_low + 0.236 * diff,
        '0.382': swing_low + 0.382 * diff,
        '0.5': swing_low + 0.5 * diff,
        '0.618': swing_low + 0.618 * diff,
        '0.786': swing_low + 0.786 * diff,
        '1.0': swing_high
    }

    latest_price = df['close'].iloc[-1]

    # ---- SMA trend filter ----
    df['sma'] = df['close'].rolling(window=sma_period).mean()
    latest_sma = df['sma'].iloc[-1]

    # ---- Determine nearest Fibonacci level ----
    nearest_level = min(levels.keys(), key=lambda k: abs(latest_price - levels[k]))
    nearest_value = levels[nearest_level]
    distance_pct = abs(latest_price - nearest_value) / nearest_value * 100 if nearest_value != 0 else 0

    # ---- Prediction logic ----
    # Primary: price relative to 0.5 level
    if latest_price > levels['0.5']:
        base = "bullish"
        base_note = "above 0.5 Fib level"
    else:
        base = "bearish"
        base_note = "below 0.5 Fib level"

    # Adjust confidence and override if price is very close to a key level
    # Key levels for reversal: 0.236 (support) and 0.786 (resistance)
    if nearest_level in ['0.236', '0.382'] and base == "bearish":
        # Price near support while below 0.5 – potential bounce, but trend still bearish
        prediction = base
        confidence = "moderate"
        note = f"Price near {nearest_level} support ({base_note}) – potential bounce but trend bearish."
    elif nearest_level in ['0.618', '0.786'] and base == "bullish":
        # Price near resistance while above 0.5 – potential pullback, but trend still bullish
        prediction = base
        confidence = "moderate"
        note = f"Price near {nearest_level} resistance ({base_note}) – potential pullback but trend bullish."
    elif nearest_level in ['0.236', '0.382'] and base == "bullish":
        # Price above 0.5 and near support – strong bullish
        prediction = "bullish"
        confidence = "high"
        note = f"Price above 0.5 and near {nearest_level} support – strong bullish."
    elif nearest_level in ['0.618', '0.786'] and base == "bearish":
        # Price below 0.5 and near resistance – strong bearish
        prediction = "bearish"
        confidence = "high"
        note = f"Price below 0.5 and near {nearest_level} resistance – strong bearish."
    else:
        # Default: use base direction with low confidence if near 0.5 or far from levels
        prediction = base
        confidence = "low"
        # If price is very close to 0.5, use SMA to break tie
        if nearest_level == '0.5' and distance_pct < 0.3:
            # Use SMA trend
            if latest_price > latest_sma:
                prediction = "bullish"
                note = "Price near 0.5 Fib, using SMA bias: bullish."
            else:
                prediction = "bearish"
                note = "Price near 0.5 Fib, using SMA bias: bearish."
            confidence = "low"
        else:
            note = f"{base_note}, not near key Fib level – mild {base} bias."

    # Last candle info
    last = df.iloc[-1]
    first = df.iloc[0]

    # ---- Extended metadata ----
    price_change = round(latest_price - first['close'], 2)
    price_change_pct = round((price_change / first['close']) * 100, 2)
    avg_volume = round(df['volume'].mean(), 0)
    high_30 = round(df['high'].max(), 2)
    low_30 = round(df['low'].min(), 2)

    # Format Fibonacci levels to 2 decimals
    fib_levels_formatted = {k: round(v, 2) for k, v in levels.items()}

    result = {
        # Core prediction
        "prediction": prediction,
        "fib_levels": fib_levels_formatted,
        "nearest_fib_level": nearest_level,
        "nearest_fib_value": round(nearest_value, 2),
        "distance_to_nearest_pct": round(distance_pct, 2),
        "swing_high": round(swing_high, 2),
        "swing_low": round(swing_low, 2),
        "sma_20": round(latest_sma, 2),
        "current_price": round(latest_price, 2),
        "last_candle_time": f"{last['date']} {last['clock']}",
        "confidence": confidence,
        "note": note,

        # Extended fields
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candle_count": len(df),
        "lookback": lookback,
        "sma_period": sma_period,
        "price_change_30": price_change,
        "price_change_percent": price_change_pct,
        "volume_last": int(last['volume']),
        "average_volume_30": int(avg_volume),
        "high_30": high_30,
        "low_30": low_30,
        "first_price": round(first['close'], 2)
    }
    return result

def main():
    try:
        with open('candles.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Error: candles.json not found.")
        return

    df = pd.DataFrame(data)
    numeric_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df.dropna(subset=numeric_cols, inplace=True)

    df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['clock'])
    df = df.sort_values('datetime').reset_index(drop=True)

    if len(df) < 30:
        print(f"Warning: only {len(df)} candles provided. Fibonacci may be unreliable.")

    try:
        prediction_meta = predict_next_5_candles_fib(df)
    except Exception as e:
        print(f"Error during prediction: {e}")
        return

    output_file = 'prediction_output.json'
    with open(output_file, 'w') as f:
        json.dump(prediction_meta, f, indent=2)

    print(f"✅ Prediction metadata written to {output_file}")
    print(json.dumps(prediction_meta, indent=2))

if __name__ == "__main__":
    main()