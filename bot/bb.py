'''
Not Use for yet
'''


import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone

def predict_next_5_candles_bb(df, period=20, num_std=2):
    """
    Predict direction for the next 5 candles based on Bollinger Bands %B.
    Uses:
      - %B = (close - lower) / (upper - lower)
      - Mean-reversion: %B < 0 => oversold => bullish; %B > 1 => overbought => bearish
      - Intermediate zones: <0.2 bullish, >0.8 bearish, else neutral
    Returns a dict with prediction metadata.
    """
    if len(df) < period:
        raise ValueError(f"Need at least {period} candles for Bollinger Bands calculation.")

    # Compute SMA (middle band)
    df['sma'] = df['close'].rolling(window=period).mean()
    # Compute rolling standard deviation
    df['std'] = df['close'].rolling(window=period).std()
    df['upper'] = df['sma'] + (df['std'] * num_std)
    df['lower'] = df['sma'] - (df['std'] * num_std)
    # %B
    denominator = df['upper'] - df['lower']
    denominator[denominator == 0] = 1e-9  # avoid division by zero
    df['pct_b'] = (df['close'] - df['lower']) / denominator

    latest_price = df['close'].iloc[-1]
    latest_pct_b = df['pct_b'].iloc[-1]
    latest_upper = df['upper'].iloc[-1]
    latest_lower = df['lower'].iloc[-1]
    latest_sma = df['sma'].iloc[-1]

    # Determine band position description
    if latest_pct_b < 0:
        band_position = "below_lower"
    elif latest_pct_b > 1:
        band_position = "above_upper"
    else:
        band_position = "inside"

    # ==== PREDICTION LOGIC (only %B) ====
    if latest_pct_b < 0:
        prediction = "bullish"
        confidence = "high" if latest_pct_b < -0.1 else "moderate"
        note = "Price below lower band – oversold, mean-reversion up likely."
    elif latest_pct_b > 1:
        prediction = "bearish"
        confidence = "high" if latest_pct_b > 1.1 else "moderate"
        note = "Price above upper band – overbought, mean-reversion down likely."
    else:
        # Inside bands: use proximity to edges
        if latest_pct_b < 0.2:
            prediction = "bullish"
            confidence = "moderate"
            note = "Price near lower band – potential bounce."
        elif latest_pct_b > 0.8:
            prediction = "bearish"
            confidence = "moderate"
            note = "Price near upper band – potential pullback."
        else:
            prediction = "neutral"
            confidence = "low"
            note = "Price in middle of bands – no clear signal."

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
        "pct_b": round(latest_pct_b, 4),
        "current_price": round(latest_price, 2),
        "upper_band": round(latest_upper, 2),
        "middle_band": round(latest_sma, 2),
        "lower_band": round(latest_lower, 2),
        "band_position": band_position,
        "last_candle_time": f"{last['date']} {last['clock']}",
        "confidence": confidence,
        "note": note,

        # Extended fields
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candle_count": len(df),
        "bb_period": period,
        "bb_std": num_std,
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

    if len(df) < 20:
        print(f"Warning: only {len(df)} candles provided. Bollinger Bands may be unreliable.")

    try:
        prediction_meta = predict_next_5_candles_bb(df)
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