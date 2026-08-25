import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone

def predict_next_5_candles_vwap(df, sma_period=20):
    """
    Predict direction for the next 5 candles based on VWAP (cumulative).
    Uses:
      - VWAP = cumulative(TP * volume) / cumulative(volume)
      - Price above VWAP -> bullish, below -> bearish
      - VWAP slope (last 5 periods) for confidence adjustment
      - SMA(20) as secondary trend filter if price is close to VWAP
    Always returns bullish or bearish (no neutral).
    """
    min_period = max(sma_period, 5) + 5
    if len(df) < min_period:
        raise ValueError(f"Need at least {min_period} candles for VWAP.")

    # ---- VWAP calculation (cumulative) ----
    df['tp'] = (df['high'] + df['low'] + df['close']) / 3  # typical price
    df['tp_vol'] = df['tp'] * df['volume']
    df['cum_tp_vol'] = df['tp_vol'].cumsum()
    df['cum_vol'] = df['volume'].cumsum()
    df['vwap'] = df['cum_tp_vol'] / df['cum_vol'].replace(0, 1e-9)

    # ---- VWAP slope (last 5 periods) ----
    def calc_slope(series):
        if len(series) < 5:
            return 0.0
        x = np.arange(len(series))
        return np.polyfit(x, series, 1)[0]

    df['vwap_slope'] = df['vwap'].rolling(5).apply(calc_slope, raw=True)

    # ---- Trend filter ----
    df['sma'] = df['close'].rolling(window=sma_period).mean()

    latest_price = df['close'].iloc[-1]
    latest_vwap = df['vwap'].iloc[-1]
    latest_slope = df['vwap_slope'].iloc[-1]
    latest_sma = df['sma'].iloc[-1]

    # ---- Determine price position relative to VWAP ----
    price_above_vwap = latest_price > latest_vwap
    diff_pct = abs(latest_price - latest_vwap) / latest_vwap * 100 if latest_vwap != 0 else 100

    # ---- Prediction logic ----
    # Primary: price vs VWAP
    if price_above_vwap:
        prediction = "bullish"
        # If VWAP slope is also rising -> higher confidence
        if latest_slope > 0:
            confidence = "high"
            note = f"Price above VWAP, VWAP rising – strong bullish."
        else:
            confidence = "moderate"
            note = f"Price above VWAP but VWAP slope flat/falling – still bullish."
    else:
        prediction = "bearish"
        if latest_slope < 0:
            confidence = "high"
            note = f"Price below VWAP, VWAP falling – strong bearish."
        else:
            confidence = "moderate"
            note = f"Price below VWAP but VWAP slope flat/rising – still bearish."

    # Adjust if price is very close to VWAP (within 0.5%) -> use SMA as tie-breaker
    if diff_pct < 0.5:
        if latest_price > latest_sma:
            prediction = "bullish"
            confidence = "low"
            note = "Price near VWAP, using SMA bias: bullish."
        else:
            prediction = "bearish"
            confidence = "low"
            note = "Price near VWAP, using SMA bias: bearish."

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
        "vwap": round(latest_vwap, 2),
        "vwap_slope": round(latest_slope, 2),
        "sma_20": round(latest_sma, 2),
        "current_price": round(latest_price, 2),
        "price_vwap_diff_pct": round(diff_pct, 2),
        "last_candle_time": f"{last['date']} {last['clock']}",
        "confidence": confidence,
        "note": note,

        # Extended fields
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candle_count": len(df),
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
        print(f"Warning: only {len(df)} candles provided. VWAP may be unreliable.")

    try:
        prediction_meta = predict_next_5_candles_vwap(df)
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