import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone

def predict_next_5_candles_ichimoku(df, tenkan_period=9, kijun_period=26, sma_period=20):
    """
    Predict direction for the next 5 candles based on Ichimoku Tenkan/Kijun crossovers.
    Uses:
      - Tenkan-sen = (highest high + lowest low) / 2 over last `tenkan_period` candles
      - Kijun-sen = (highest high + lowest low) / 2 over last `kijun_period` candles
      - Crossover detection (current vs previous)
      - Current position: Tenkan above Kijun -> bullish, below -> bearish
      - Confidence: high if just crossed, moderate if aligned, low if recent cross conflict
    Always returns bullish or bearish (no neutral).
    """
    if len(df) < max(kijun_period, sma_period) + 1:
        raise ValueError(f"Need at least {max(kijun_period, sma_period)} candles.")

    # ---- Tenkan-sen (9) ----
    df['tenkan_high'] = df['high'].rolling(window=tenkan_period).max()
    df['tenkan_low'] = df['low'].rolling(window=tenkan_period).min()
    df['tenkan'] = (df['tenkan_high'] + df['tenkan_low']) / 2

    # ---- Kijun-sen (26) ----
    df['kijun_high'] = df['high'].rolling(window=kijun_period).max()
    df['kijun_low'] = df['low'].rolling(window=kijun_period).min()
    df['kijun'] = (df['kijun_high'] + df['kijun_low']) / 2

    # ---- SMA(20) trend filter ----
    df['sma'] = df['close'].rolling(window=sma_period).mean()

    # ---- Current values ----
    latest_tenkan = df['tenkan'].iloc[-1]
    latest_kijun = df['kijun'].iloc[-1]
    latest_price = df['close'].iloc[-1]
    latest_sma = df['sma'].iloc[-1]

    # ---- Crossover detection ----
    if len(df) >= 2:
        prev_tenkan = df['tenkan'].iloc[-2]
        prev_kijun = df['kijun'].iloc[-2]
        if pd.isna(prev_tenkan) or pd.isna(prev_kijun):
            crossover = "none"
        else:
            if prev_tenkan <= prev_kijun and latest_tenkan > latest_kijun:
                crossover = "bullish_cross"
            elif prev_tenkan >= prev_kijun and latest_tenkan < latest_kijun:
                crossover = "bearish_cross"
            else:
                crossover = "none"
    else:
        crossover = "none"

    # ---- Determine current position ----
    if latest_tenkan > latest_kijun:
        position = "tenkan_above"
        base = "bullish"
    elif latest_tenkan < latest_kijun:
        position = "tenkan_below"
        base = "bearish"
    else:
        # Equal – use SMA trend
        base = "bullish" if latest_price > latest_sma else "bearish"
        position = "equal"

    # ---- Prediction logic ----
    # 1. Just crossed -> high confidence
    if crossover == "bullish_cross":
        prediction = "bullish"
        confidence = "high"
        note = "Tenkan crossed above Kijun – strong bullish signal."
    elif crossover == "bearish_cross":
        prediction = "bearish"
        confidence = "high"
        note = "Tenkan crossed below Kijun – strong bearish signal."

    # 2. No crossover: use current position
    else:
        if position == "tenkan_above":
            prediction = "bullish"
            # If also price above SMA -> moderate, else low
            if latest_price > latest_sma:
                confidence = "moderate"
                note = "Tenkan above Kijun and price above SMA – bullish bias."
            else:
                confidence = "low"
                note = "Tenkan above Kijun but price below SMA – bullish but weak."
        elif position == "tenkan_below":
            prediction = "bearish"
            if latest_price < latest_sma:
                confidence = "moderate"
                note = "Tenkan below Kijun and price below SMA – bearish bias."
            else:
                confidence = "low"
                note = "Tenkan below Kijun but price above SMA – bearish but weak."
        else:  # equal
            # Use SMA trend
            prediction = "bullish" if latest_price > latest_sma else "bearish"
            confidence = "low"
            note = f"Tenkan=Kijun, using SMA trend: {prediction}."

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
        "tenkan": round(latest_tenkan, 2),
        "kijun": round(latest_kijun, 2),
        "crossover": crossover,
        "position": position,
        "sma_20": round(latest_sma, 2),
        "current_price": round(latest_price, 2),
        "last_candle_time": f"{last['date']} {last['clock']}",
        "confidence": confidence,
        "note": note,

        # Extended fields
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candle_count": len(df),
        "tenkan_period": tenkan_period,
        "kijun_period": kijun_period,
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
        print(f"Warning: only {len(df)} candles provided. Ichimoku may be unreliable.")

    try:
        prediction_meta = predict_next_5_candles_ichimoku(df)
    except Exception as e:
        print(f"Error during prediction: {e}")
        return

    output_file = 'Ichimoku_prediction_output.json'
    with open(output_file, 'w') as f:
        json.dump(prediction_meta, f, indent=2)

    print(f"✅ Prediction metadata written to {output_file}")
    print(json.dumps(prediction_meta, indent=2))

if __name__ == "__main__":
    main()