import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone

def predict_next_5_candles_macd(df, fast=12, slow=26, signal=9):
    """
    Predict direction for the next 5 candles based on MACD histogram slope.
    Uses:
      - MACD line = EMA(fast) - EMA(slow)
      - Signal line = EMA(signal) of MACD line
      - Histogram = MACD line - Signal line
      - Slope of histogram over last 3 periods (linear regression)
    Returns a dict with prediction metadata.
    """
    min_period = max(fast, slow, signal) + 3
    if len(df) < min_period:
        raise ValueError(f"Need at least {min_period} candles for MACD calculation.")

    # Compute EMAs
    df['ema_fast'] = df['close'].ewm(span=fast, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=slow, adjust=False).mean()
    df['macd'] = df['ema_fast'] - df['ema_slow']
    df['signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
    df['hist'] = df['macd'] - df['signal']  # histogram

    # Slope of histogram using linear regression over last 3 periods
    def calc_slope(series):
        if len(series) < 3:
            return 0.0
        x = np.arange(len(series))
        slope = np.polyfit(x, series, 1)[0]
        return slope

    df['hist_slope'] = df['hist'].rolling(3).apply(calc_slope, raw=True)

    latest_price = df['close'].iloc[-1]
    latest_hist = df['hist'].iloc[-1]
    latest_slope = df['hist_slope'].iloc[-1]
    latest_macd = df['macd'].iloc[-1]
    latest_signal = df['signal'].iloc[-1]

    # Determine if histogram is positive or negative
    hist_position = "positive" if latest_hist > 0 else "negative" if latest_hist < 0 else "zero"

    # ==== PREDICTION LOGIC (based on histogram slope + position) ====
    # Primary: slope direction
    if latest_slope > 0.001:  # small threshold to avoid noise
        base = "bullish"
        slope_signal = "rising"
    elif latest_slope < -0.001:
        base = "bearish"
        slope_signal = "falling"
    else:
        base = "neutral"
        slope_signal = "flat"

    # Adjust confidence based on histogram position
    if hist_position == "positive" and base == "bullish":
        prediction = "bullish"
        confidence = "high"
        note = "Histogram positive and rising – strong bullish momentum."
    elif hist_position == "negative" and base == "bearish":
        prediction = "bearish"
        confidence = "high"
        note = "Histogram negative and falling – strong bearish momentum."
    elif hist_position == "positive" and base == "bearish":
        prediction = "neutral"
        confidence = "moderate"
        note = "Histogram positive but falling – momentum weakening (bullish divergence?)."
    elif hist_position == "negative" and base == "bullish":
        prediction = "neutral"
        confidence = "moderate"
        note = "Histogram negative but rising – momentum weakening (bearish divergence?)."
    else:
        # either slope is flat or conflicting signals
        if latest_hist > 0:
            prediction = "bullish"
            confidence = "low"
            note = "Histogram positive but slope neutral – mild bullish bias."
        elif latest_hist < 0:
            prediction = "bearish"
            confidence = "low"
            note = "Histogram negative but slope neutral – mild bearish bias."
        else:
            prediction = "neutral"
            confidence = "low"
            note = "Histogram near zero and slope flat – no clear signal."

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
        "macd_hist": round(latest_hist, 4),
        "macd_line": round(latest_macd, 4),
        "signal_line": round(latest_signal, 4),
        "hist_slope": round(latest_slope, 4),
        "slope_signal": slope_signal,
        "hist_position": hist_position,
        "current_price": round(latest_price, 2),
        "last_candle_time": f"{last['date']} {last['clock']}",
        "confidence": confidence,
        "note": note,

        # Extended fields
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candle_count": len(df),
        "macd_fast": fast,
        "macd_slow": slow,
        "macd_signal": signal,
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
        print(f"Warning: only {len(df)} candles provided. MACD may be unreliable.")

    try:
        prediction_meta = predict_next_5_candles_macd(df)
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