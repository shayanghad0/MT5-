import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone

def predict_next_5_candles_stoch(df, k_period=14, d_period=3, smooth=3):
    """
    Predict direction for the next 5 candles based on Stochastic Oscillator.
    Always returns bullish or bearish (no neutral) using:
      - Oversold (<20) => bullish (high confidence if %K < 10)
      - Overbought (>80) => bearish (high confidence if %K > 90)
      - Crossover detection: %K crosses above %D => bullish, below => bearish
    Confidence: high if strong signal, else low.
    """
    min_period = max(k_period, d_period + smooth) + 1
    if len(df) < min_period:
        raise ValueError(f"Need at least {min_period} candles for Stochastic.")

    # Compute %K: (close - lowest low) / (highest high - lowest low) * 100
    df['lowest_low'] = df['low'].rolling(window=k_period).min()
    df['highest_high'] = df['high'].rolling(window=k_period).max()
    denominator = df['highest_high'] - df['lowest_low']
    denominator[denominator == 0] = 1e-9  # avoid division by zero
    df['k_raw'] = 100 * ((df['close'] - df['lowest_low']) / denominator)

    # %D = SMA of %K (usually 3-period)
    df['k'] = df['k_raw'].rolling(window=smooth).mean()
    df['d'] = df['k'].rolling(window=d_period).mean()

    latest_k = df['k'].iloc[-1]
    latest_d = df['d'].iloc[-1]
    latest_price = df['close'].iloc[-1]

    # Crossover detection: compare current with previous
    if len(df) >= 2:
        prev_k = df['k'].iloc[-2]
        prev_d = df['d'].iloc[-2]
        crossover = None
        if prev_k < prev_d and latest_k > latest_d:
            crossover = "bullish_cross"
        elif prev_k > prev_d and latest_k < latest_d:
            crossover = "bearish_cross"
        else:
            crossover = "none"
    else:
        crossover = "none"

    # ==== PREDICTION LOGIC (no neutral) ====
    # 1. Overbought/Oversold zones (mean-reversion)
    if latest_k < 20:
        prediction = "bullish"
        confidence = "high" if latest_k < 10 else "moderate"
        note = f"Oversold (%K={latest_k:.1f}) – potential bounce."
    elif latest_k > 80:
        prediction = "bearish"
        confidence = "high" if latest_k > 90 else "moderate"
        note = f"Overbought (%K={latest_k:.1f}) – potential pullback."
    else:
        # 2. Use crossover as directional signal
        if crossover == "bullish_cross":
            prediction = "bullish"
            confidence = "moderate"
            note = f"%K crossed above %D – bullish momentum."
        elif crossover == "bearish_cross":
            prediction = "bearish"
            confidence = "moderate"
            note = f"%K crossed below %D – bearish momentum."
        else:
            # 3. If no crossover and not extreme, use position relative to 50
            if latest_k > 50:
                prediction = "bullish"
                confidence = "low"
                note = f"%K above 50 ({latest_k:.1f}) – mild bullish bias."
            else:
                prediction = "bearish"
                confidence = "low"
                note = f"%K below 50 ({latest_k:.1f}) – mild bearish bias."

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
        "stoch_k": round(latest_k, 2),
        "stoch_d": round(latest_d, 2),
        "crossover": crossover,
        "current_price": round(latest_price, 2),
        "last_candle_time": f"{last['date']} {last['clock']}",
        "confidence": confidence,
        "note": note,

        # Extended fields
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candle_count": len(df),
        "stoch_k_period": k_period,
        "stoch_d_period": d_period,
        "stoch_smooth": smooth,
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
        print(f"Warning: only {len(df)} candles provided. Stochastic may be unreliable.")

    try:
        prediction_meta = predict_next_5_candles_stoch(df)
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