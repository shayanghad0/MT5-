import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone

def predict_next_5_candles_stoch(df, k_period=14, d_period=3, smooth=3, sma_period=20):
    """
    Predict direction for the next 5 candles based on Stochastic + trend filter.
    Always returns bullish or bearish.
    Uses:
      - Oversold (<20) => bullish (high confidence if %K < 10) BUT overridden by trend.
      - Overbought (>80) => bearish.
      - Crossover detection with trend confirmation.
      - Price vs 20-SMA as primary trend filter.
    """
    min_period = max(k_period, d_period + smooth, sma_period) + 1
    if len(df) < min_period:
        raise ValueError(f"Need at least {min_period} candles for Stochastic.")

    # ---- Stochastic ----
    df['lowest_low'] = df['low'].rolling(window=k_period).min()
    df['highest_high'] = df['high'].rolling(window=k_period).max()
    denominator = df['highest_high'] - df['lowest_low']
    denominator[denominator == 0] = 1e-9
    df['k_raw'] = 100 * ((df['close'] - df['lowest_low']) / denominator)
    df['k'] = df['k_raw'].rolling(window=smooth).mean()
    df['d'] = df['k'].rolling(window=d_period).mean()

    # ---- Trend filter ----
    df['sma'] = df['close'].rolling(window=sma_period).mean()

    latest_k = df['k'].iloc[-1]
    latest_d = df['d'].iloc[-1]
    latest_price = df['close'].iloc[-1]
    latest_sma = df['sma'].iloc[-1]

    # Crossover detection
    if len(df) >= 2:
        prev_k = df['k'].iloc[-2]
        prev_d = df['d'].iloc[-2]
        if prev_k < prev_d and latest_k > latest_d:
            crossover = "bullish_cross"
        elif prev_k > prev_d and latest_k < latest_d:
            crossover = "bearish_cross"
        else:
            crossover = "none"
    else:
        crossover = "none"

    # ---- Trend direction ----
    trend_bullish = latest_price > latest_sma
    distance_pct = abs(latest_price - latest_sma) / latest_sma * 100 if latest_sma != 0 else 100

    # ---- Prediction logic with trend override ----
    # 1. Overbought (>80) => always bearish
    if latest_k > 80:
        prediction = "bearish"
        confidence = "high" if latest_k > 90 else "moderate"
        note = f"Overbought (%K={latest_k:.1f}) – bearish reversal likely."

    # 2. Oversold (<20) – bullish but only if trend agrees or extremely oversold
    elif latest_k < 20:
        # Strong oversold (<10) can override even strong downtrend
        if latest_k < 10:
            prediction = "bullish"
            confidence = "high"
            note = f"Extreme oversold (%K={latest_k:.1f}) – strong bounce potential."
        elif trend_bullish:
            prediction = "bullish"
            confidence = "moderate"
            note = f"Oversold (%K={latest_k:.1f}) with bullish trend – bounce likely."
        else:
            # Oversold but in downtrend – stay bearish
            prediction = "bearish"
            confidence = "low"
            note = f"Oversold (%K={latest_k:.1f}) but price below SMA – downtrend persists."

    # 3. Neutral zone (20-80) – use crossover + trend
    else:
        if crossover == "bullish_cross":
            if trend_bullish:
                prediction = "bullish"
                confidence = "moderate"
                note = "%K crossed above %D with bullish trend."
            else:
                # Bearish trend overrides bullish crossover
                prediction = "bearish"
                confidence = "low"
                note = "%K crossed above %D but price below SMA – likely fakeout."
        elif crossover == "bearish_cross":
            prediction = "bearish"
            confidence = "moderate" if not trend_bullish else "low"
            note = "%K crossed below %D – bearish signal."
        else:
            # No crossover – use trend bias
            if trend_bullish:
                prediction = "bullish"
                confidence = "low"
                note = f"Stochastic mid-range ({latest_k:.1f}) with bullish trend."
            else:
                prediction = "bearish"
                confidence = "low"
                note = f"Stochastic mid-range ({latest_k:.1f}) with bearish trend."

    # Last candle info
    last = df.iloc[-1]
    first = df.iloc[0]

    # Extra metadata
    price_change = round(latest_price - first['close'], 2)
    price_change_pct = round((price_change / first['close']) * 100, 2)
    avg_volume = round(df['volume'].mean(), 0)
    high_30 = round(df['high'].max(), 2)
    low_30 = round(df['low'].min(), 2)

    result = {
        "prediction": prediction,
        "stoch_k": round(latest_k, 2),
        "stoch_d": round(latest_d, 2),
        "crossover": crossover,
        "sma_20": round(latest_sma, 2),
        "trend": "bullish" if trend_bullish else "bearish",
        "current_price": round(latest_price, 2),
        "last_candle_time": f"{last['date']} {last['clock']}",
        "confidence": confidence,
        "note": note,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candle_count": len(df),
        "stoch_k_period": k_period,
        "stoch_d_period": d_period,
        "stoch_smooth": smooth,
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
        print(f"Warning: only {len(df)} candles provided. Results may be unreliable.")

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