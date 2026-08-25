import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone

def predict_next_5_candles_macd(df, fast=12, slow=26, signal=9):
    """
    Predict direction for the next 5 candles based on MACD histogram.
    Always returns bullish/bearish (no neutral) based on histogram sign.
    Confidence: high if slope agrees with position, else low.
    """
    min_period = max(fast, slow, signal) + 3
    if len(df) < min_period:
        raise ValueError(f"Need at least {min_period} candles for MACD.")

    # Compute MACD
    df['ema_fast'] = df['close'].ewm(span=fast, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=slow, adjust=False).mean()
    df['macd'] = df['ema_fast'] - df['ema_slow']
    df['signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
    df['hist'] = df['macd'] - df['signal']

    # Histogram slope (last 3 periods)
    def calc_slope(series):
        if len(series) < 3:
            return 0.0
        x = np.arange(len(series))
        return np.polyfit(x, series, 1)[0]

    df['hist_slope'] = df['hist'].rolling(3).apply(calc_slope, raw=True)

    latest_price = df['close'].iloc[-1]
    latest_hist = df['hist'].iloc[-1]
    latest_slope = df['hist_slope'].iloc[-1]
    latest_macd = df['macd'].iloc[-1]
    latest_signal = df['signal'].iloc[-1]

    # ==== PREDICTION: ALWAYS BULLISH OR BEARISH ====
    if latest_hist > 0:
        prediction = "bullish"
        hist_pos = "positive"
    else:
        prediction = "bearish"
        hist_pos = "negative"

    # Confidence: high if slope agrees with position
    if hist_pos == "positive" and latest_slope > 0:
        confidence = "high"
        note = "Histogram positive and rising – strong bullish momentum."
    elif hist_pos == "negative" and latest_slope < 0:
        confidence = "high"
        note = "Histogram negative and falling – strong bearish momentum."
    else:
        confidence = "low"
        if hist_pos == "positive" and latest_slope < 0:
            note = "Histogram positive but falling – bullish momentum weakening."
        elif hist_pos == "negative" and latest_slope > 0:
            note = "Histogram negative but rising – bearish momentum weakening."
        else:
            note = f"Histogram {hist_pos} with flat slope – mild {prediction} bias."

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
        "hist_position": hist_pos,
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

    output_file = 'MACD_prediction_output.json'
    with open(output_file, 'w') as f:
        json.dump(prediction_meta, f, indent=2)

    print(f"✅ Prediction metadata written to {output_file}")
    print(json.dumps(prediction_meta, indent=2))

if __name__ == "__main__":
    main()