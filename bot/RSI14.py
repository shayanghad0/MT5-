import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone

def compute_rsi(data, period=14):
    """
    Compute RSI (Relative Strength Index) for the given price series.
    data: pandas Series of close prices
    returns: pandas Series of RSI values
    """
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, 1e-9)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def predict_next_5_candles(df):
    """
    Predict direction for the next 5 candles based on RSI(14) and a simple EMA trend.
    Returns a dict with prediction metadata.
    (Logic is exactly as requested – no changes here.)
    """
    if len(df) < 30:
        raise ValueError("Need at least 30 candles for reliable RSI calculation.")

    # Compute RSI
    df['rsi'] = compute_rsi(df['close'], 14)
    latest_rsi = df['rsi'].iloc[-1]

    # EMA(9)
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    latest_close = df['close'].iloc[-1]
    latest_ema9 = df['ema_9'].iloc[-1]

    # RSI status
    if latest_rsi < 30:
        rsi_status = "oversold"
    elif latest_rsi > 70:
        rsi_status = "overbought"
    else:
        rsi_status = "neutral"

    # ==== PREDICTION LOGIC (unchanged) ====
    if latest_rsi < 30:
        prediction = "bullish"
        confidence = "high" if latest_rsi < 25 else "moderate"
    elif latest_rsi > 70:
        prediction = "bearish"
        confidence = "high" if latest_rsi > 75 else "moderate"
    else:
        if latest_close >= latest_ema9 - 1e-9:
            prediction = "bullish"
            confidence = "low"
        else:
            prediction = "bearish"
            confidence = "low"

    note = ""
    if latest_rsi < 30 and latest_close < latest_ema9:
        note = "Oversold but price below EMA(9) – potential continuation of downtrend."
    elif latest_rsi > 70 and latest_close > latest_ema9:
        note = "Overbought but price above EMA(9) – potential continuation of uptrend."

    # Last candle info
    last = df.iloc[-1]
    first = df.iloc[0]

    # ==== EXTRA METADATA (output only, not used in prediction) ====
    price_change = round(latest_close - first['close'], 2)
    price_change_pct = round((price_change / first['close']) * 100, 2)
    avg_volume = round(df['volume'].mean(), 0)
    high_30 = round(df['high'].max(), 2)
    low_30 = round(df['low'].min(), 2)

    result = {
        # Core prediction (unchanged)
        "prediction": prediction,
        "rsi": round(latest_rsi, 2),
        "rsi_status": rsi_status,
        "current_price": round(latest_close, 2),
        "ema_9": round(latest_ema9, 2),
        "last_candle_time": f"{last['date']} {last['clock']}",
        "confidence": confidence,
        "note": note,

        # Extended fields (new, longer JSON)
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candle_count": len(df),
        "rsi_period": 14,
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
        print(f"Warning: only {len(df)} candles provided. RSI may be unreliable.")

    try:
        prediction_meta = predict_next_5_candles(df)
    except Exception as e:
        print(f"Error during prediction: {e}")
        return

    output_file = 'RSI14_prediction_output.json'
    with open(output_file, 'w') as f:
        json.dump(prediction_meta, f, indent=2)

    print(f"✅ Prediction metadata written to {output_file}")
    print(json.dumps(prediction_meta, indent=2))

if __name__ == "__main__":
    main()