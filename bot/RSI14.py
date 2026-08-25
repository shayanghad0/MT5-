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
    rs = gain / loss.replace(0, 1e-9)          # avoid division by zero
    rsi = 100 - (100 / (1 + rs))
    return rsi

def predict_next_5_candles(df):
    """
    Predict direction for the next 5 candles based on RSI(14) and a simple EMA trend.
    Returns a dict with prediction metadata.
    """
    # Ensure we have at least 30 candles
    if len(df) < 30:
        raise ValueError("Need at least 30 candles for reliable RSI calculation.")

    # Compute RSI
    df['rsi'] = compute_rsi(df['close'], 14)
    latest_rsi = df['rsi'].iloc[-1]

    # Compute EMA(9) for trend confirmation
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    latest_close = df['close'].iloc[-1]
    latest_ema9 = df['ema_9'].iloc[-1]

    # Determine overbought/oversold status
    if latest_rsi < 30:
        rsi_status = "oversold"
    elif latest_rsi > 70:
        rsi_status = "overbought"
    else:
        rsi_status = "neutral"

    # Base prediction on RSI
    if latest_rsi < 30:
        prediction = "bullish"
        confidence = "high" if latest_rsi < 25 else "moderate"
    elif latest_rsi > 70:
        prediction = "bearish"
        confidence = "high" if latest_rsi > 75 else "moderate"
    else:
        # In neutral RSI, use EMA trend as tie-breaker
        # Use a small tolerance to avoid equality being treated as bearish
        if latest_close >= latest_ema9 - 1e-9:
            prediction = "bullish"
            confidence = "low"
        else:
            prediction = "bearish"
            confidence = "low"

    # Additional note if trend contradicts RSI
    note = ""
    if latest_rsi < 30 and latest_close < latest_ema9:
        note = "Oversold but price below EMA(9) – potential continuation of downtrend."
    elif latest_rsi > 70 and latest_close > latest_ema9:
        note = "Overbought but price above EMA(9) – potential continuation of uptrend."

    # Build result
    last_candle = df.iloc[-1]
    result = {
        "prediction": prediction,
        "rsi": round(latest_rsi, 2),
        "rsi_status": rsi_status,
        "current_price": round(latest_close, 2),
        "ema_9": round(latest_ema9, 2),
        "last_candle_time": f"{last_candle['date']} {last_candle['clock']}",
        "confidence": confidence,
        "note": note,
        "timestamp": datetime.now(timezone.utc).isoformat()  # fixed deprecation
    }
    return result

def main():
    # Read candles.json
    try:
        with open('candles.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Error: candles.json not found in the current directory.")
        return

    # Convert to DataFrame
    df = pd.DataFrame(data)
    # Ensure numeric columns
    numeric_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df.dropna(subset=numeric_cols, inplace=True)

    # Sort by date and time (assuming data is already in order, but just in case)
    df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['clock'])
    df = df.sort_values('datetime').reset_index(drop=True)

    # Validate we have enough data
    if len(df) < 30:
        print(f"Warning: only {len(df)} candles provided. RSI may be unreliable.")
        # Still attempt to compute with available data, but we'll use all.

    # Compute prediction
    try:
        prediction_meta = predict_next_5_candles(df)
    except Exception as e:
        print(f"Error during prediction: {e}")
        return

    # Write output to prediction_output.json
    output_file = 'prediction_output.json'
    with open(output_file, 'w') as f:
        json.dump(prediction_meta, f, indent=2)

    print(f"✅ Prediction metadata written to {output_file}")
    print(json.dumps(prediction_meta, indent=2))

if __name__ == "__main__":
    main()