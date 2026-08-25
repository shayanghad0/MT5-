import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone

def predict_next_5_candles_obv(df, obv_period=14, sma_period=20):
    """
    Predict direction for the next 5 candles based on On-Balance Volume (OBV).
    Always returns bullish or bearish (no neutral) using:
      - OBV slope (last 5 periods) – momentum of volume
      - Price trend vs SMA(20) – primary trend filter
      - Divergence detection: OBV up while price down -> bullish divergence (and vice versa)
    Confidence: high if OBV and price agree strongly, low if conflict.
    """
    min_period = max(obv_period, sma_period) + 5
    if len(df) < min_period:
        raise ValueError(f"Need at least {min_period} candles for OBV.")

    # ---- OBV calculation ----
    # OBV: if close > previous close, add volume; if close < previous, subtract; else unchanged
    df['obv'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()

    # ---- OBV slope (last 5 periods) ----
    def calc_slope(series):
        if len(series) < 5:
            return 0.0
        x = np.arange(len(series))
        return np.polyfit(x, series, 1)[0]

    df['obv_slope'] = df['obv'].rolling(5).apply(calc_slope, raw=True)

    # ---- Trend filter ----
    df['sma'] = df['close'].rolling(window=sma_period).mean()

    # ---- Normalize OBV slope for better interpretation ----
    # We'll compare slope direction, not magnitude
    latest_price = df['close'].iloc[-1]
    latest_sma = df['sma'].iloc[-1]
    latest_obv = df['obv'].iloc[-1]
    latest_slope = df['obv_slope'].iloc[-1]
    trend_bullish = latest_price > latest_sma

    # Determine if OBV slope is positive, negative, or flat
    slope_threshold = 1e-6  # small tolerance for flat
    if latest_slope > slope_threshold:
        obv_trend = "rising"
    elif latest_slope < -slope_threshold:
        obv_trend = "falling"
    else:
        obv_trend = "flat"

    # ---- Divergence detection ----
    # Price change over last 5 candles
    price_change_5 = latest_price - df['close'].iloc[-5] if len(df) >= 5 else 0
    obv_change_5 = latest_obv - df['obv'].iloc[-5] if len(df) >= 5 else 0

    # Divergence: price down, OBV up -> bullish; price up, OBV down -> bearish
    if price_change_5 < 0 and obv_change_5 > 0:
        divergence = "bullish_divergence"
    elif price_change_5 > 0 and obv_change_5 < 0:
        divergence = "bearish_divergence"
    else:
        divergence = "none"

    # ---- Prediction logic ----
    # 1. Divergence overrides: strongly predictive
    if divergence == "bullish_divergence":
        prediction = "bullish"
        confidence = "high"
        note = "Bullish divergence: price down but OBV up – potential reversal up."
    elif divergence == "bearish_divergence":
        prediction = "bearish"
        confidence = "high"
        note = "Bearish divergence: price up but OBV down – potential reversal down."

    # 2. No divergence: use trend + OBV slope
    else:
        # If trend and OBV slope agree -> strong signal
        if (trend_bullish and obv_trend == "rising") or (not trend_bullish and obv_trend == "falling"):
            prediction = "bullish" if trend_bullish else "bearish"
            confidence = "moderate"
            note = f"Trend and OBV agree: {prediction} momentum."
        # If OBV slope is flat, use only trend
        elif obv_trend == "flat":
            prediction = "bullish" if trend_bullish else "bearish"
            confidence = "low"
            note = f"OBV flat, using SMA trend: {prediction}."
        # If trend and OBV disagree -> conflict, use price trend (SMA) with low confidence
        else:
            prediction = "bullish" if trend_bullish else "bearish"
            confidence = "low"
            note = f"OBV {obv_trend} but price trend {prediction} – conflicting signals, using price trend."

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
        "obv": round(latest_obv, 2),
        "obv_slope": round(latest_slope, 2),
        "obv_trend": obv_trend,
        "divergence": divergence,
        "sma_20": round(latest_sma, 2),
        "current_price": round(latest_price, 2),
        "last_candle_time": f"{last['date']} {last['clock']}",
        "confidence": confidence,
        "note": note,

        # Extended fields
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candle_count": len(df),
        "obv_period": obv_period,
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
        print(f"Warning: only {len(df)} candles provided. OBV may be unreliable.")

    try:
        prediction_meta = predict_next_5_candles_obv(df)
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