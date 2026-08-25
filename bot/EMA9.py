import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone

def predict_next_5_candles_ema(df, period=9):
    """
    Predict direction for the next 5 candles based on EMA(9).
    Uses:
      - Price relative to EMA (above = bullish, below = bearish)
      - EMA slope (rising = confidence boost for bullish, falling for bearish)
    Returns a dict with prediction metadata.
    """
    if len(df) < period:
        raise ValueError(f"Need at least {period} candles for EMA calculation.")

    # Compute EMA(9)
    df['ema_9'] = df['close'].ewm(span=period, adjust=False).mean()
    latest_price = df['close'].iloc[-1]
    latest_ema = df['ema_9'].iloc[-1]

    # Compute EMA slope (change over last 3 periods)
    if len(df) >= 3:
        ema_prev = df['ema_9'].iloc[-3]
        ema_slope = latest_ema - ema_prev
    else:
        ema_slope = 0.0

    # Determine position relative to EMA
    if latest_price > latest_ema:
        price_position = "above"
    elif latest_price < latest_ema:
        price_position = "below"
    else:
        price_position = "equal"

    # ==== PREDICTION LOGIC (only EMA) ====
    if price_position == "above":
        prediction = "bullish"
        # If EMA is rising, confidence is higher
        confidence = "high" if ema_slope > 0 else "moderate"
    elif price_position == "below":
        prediction = "bearish"
        confidence = "high" if ema_slope < 0 else "moderate"
    else:  # equal
        prediction = "neutral"
        confidence = "low"

    # Additional note (contradictions / strong signals)
    note = ""
    if price_position == "above" and ema_slope < 0:
        note = "Price above EMA but EMA is falling – potential fakeout."
    elif price_position == "below" and ema_slope > 0:
        note = "Price below EMA but EMA is rising – potential reversal."

    # Last candle info
    last = df.iloc[-1]
    first = df.iloc[0]

    # ==== EXTRA METADATA ====
    price_change = round(latest_price - first['close'], 2)
    price_change_pct = round((price_change / first['close']) * 100, 2)
    avg_volume = round(df['volume'].mean(), 0)
    high_30 = round(df['high'].max(), 2)
    low_30 = round(df['low'].min(), 2)

    result = {
        # Core prediction
        "prediction": prediction,
        "ema_9": round(latest_ema, 2),
        "current_price": round(latest_price, 2),
        "price_position": price_position,          # above / below / equal
        "ema_slope": round(ema_slope, 4),
        "last_candle_time": f"{last['date']} {last['clock']}",
        "confidence": confidence,
        "note": note,

        # Extended fields
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candle_count": len(df),
        "ema_period": period,
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

    if len(df) < 9:
        print(f"Warning: only {len(df)} candles provided. EMA may be unreliable.")

    try:
        prediction_meta = predict_next_5_candles_ema(df)
    except Exception as e:
        print(f"Error during prediction: {e}")
        return

    output_file = 'EMA9_prediction_output.json'
    with open(output_file, 'w') as f:
        json.dump(prediction_meta, f, indent=2)

    print(f"✅ Prediction metadata written to {output_file}")
    print(json.dumps(prediction_meta, indent=2))

if __name__ == "__main__":
    main()