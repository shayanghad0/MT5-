import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone

def predict_next_5_candles_lr(df, period=5, sma_period=20):
    """
    Predict direction for the next 5 candles based on Linear Regression Slope (5-period).
    Uses:
      - Linear regression slope of close prices over last `period` candles.
      - Positive slope -> bullish, negative -> bearish.
      - Slope magnitude determines confidence: |slope| > threshold -> high, else low.
      - SMA(20) trend filter used when slope is near zero (tie‑breaker).
    Always returns bullish or bearish (no neutral).
    """
    if len(df) < max(period, sma_period) + 1:
        raise ValueError(f"Need at least {max(period, sma_period)} candles.")

    # ---- Linear Regression Slope (5-period) ----
    def calc_slope(series):
        if len(series) < 2:
            return 0.0
        x = np.arange(len(series))
        slope = np.polyfit(x, series, 1)[0]
        return slope

    df['lr_slope'] = df['close'].rolling(period).apply(calc_slope, raw=True)

    # ---- SMA(20) trend filter ----
    df['sma'] = df['close'].rolling(window=sma_period).mean()

    latest_price = df['close'].iloc[-1]
    latest_slope = df['lr_slope'].iloc[-1]
    latest_sma = df['sma'].iloc[-1]

    # ---- Determine slope direction ----
    # Small threshold to avoid noise
    slope_threshold = 0.001 * latest_price if latest_price != 0 else 0.001

    if latest_slope > slope_threshold:
        prediction = "bullish"
        slope_dir = "rising"
    elif latest_slope < -slope_threshold:
        prediction = "bearish"
        slope_dir = "falling"
    else:
        # Slope is near zero – use SMA trend as tie‑breaker
        if latest_price > latest_sma:
            prediction = "bullish"
            slope_dir = "flat"
        else:
            prediction = "bearish"
            slope_dir = "flat"

    # ---- Confidence based on slope magnitude ----
    # Use a relative threshold: consider slope magnitude relative to price
    if slope_dir != "flat":
        abs_slope_pct = abs(latest_slope) / latest_price * 100 if latest_price != 0 else 0
        if abs_slope_pct > 0.5:  # slope > 0.5% of price per period
            confidence = "high"
        elif abs_slope_pct > 0.2:
            confidence = "moderate"
        else:
            confidence = "low"
    else:
        confidence = "low"

    # ---- Note ----
    if slope_dir == "rising":
        note = f"Linear regression slope positive ({latest_slope:.4f}) – bullish momentum."
    elif slope_dir == "falling":
        note = f"Linear regression slope negative ({latest_slope:.4f}) – bearish momentum."
    else:
        note = f"Slope near zero, using SMA trend: {prediction}."

    # Last candle info
    last = df.iloc[-1]
    first = df.iloc[0]

    # ---- Extended metadata ----
    price_change = round(latest_price - first['close'], 2)
    price_change_pct = round((price_change / first['close']) * 100, 2)
    avg_volume = round(df['volume'].mean(), 0)
    high_30 = round(df['high'].max(), 2)
    low_30 = round(df['low'].min(), 2)

    result = {
        # Core prediction
        "prediction": prediction,
        "lr_slope": round(latest_slope, 4),
        "slope_direction": slope_dir,
        "sma_20": round(latest_sma, 2),
        "current_price": round(latest_price, 2),
        "last_candle_time": f"{last['date']} {last['clock']}",
        "confidence": confidence,
        "note": note,

        # Extended fields
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candle_count": len(df),
        "lr_period": period,
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
        print(f"Warning: only {len(df)} candles provided. LR slope may be unreliable.")

    try:
        prediction_meta = predict_next_5_candles_lr(df)
    except Exception as e:
        print(f"Error during prediction: {e}")
        return

    output_file = 'LinearRegression_prediction_output.json'
    with open(output_file, 'w') as f:
        json.dump(prediction_meta, f, indent=2)

    print(f"✅ Prediction metadata written to {output_file}")
    print(json.dumps(prediction_meta, indent=2))

if __name__ == "__main__":
    main()