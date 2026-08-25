import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone

def compute_atr(df, period=14):
    high = df['high']
    low = df['low']
    close = df['close'].shift()
    tr1 = high - low
    tr2 = (high - close).abs()
    tr3 = (low - close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def predict_next_5_candles(df, atr_period=14, sma_period=20):
    """
    Predicts direction (bearish/bullish/neutral) based on price vs SMA(20),
    and also reports ATR(14) volatility regime.
    """
    if len(df) < max(atr_period, sma_period) + 5:
        raise ValueError("Not enough candles.")

    # --- ATR calculation ---
    df['atr'] = compute_atr(df, atr_period)
    df['atr_ma'] = df['atr'].rolling(window=5).mean()
    latest_atr = df['atr'].iloc[-1]
    latest_atr_ma = df['atr_ma'].iloc[-1]
    atr_history = df['atr'].iloc[-min(30, len(df)):]
    percentile = (atr_history < latest_atr).sum() / len(atr_history) * 100

    # --- SMA trend filter ---
    df['sma'] = df['close'].rolling(window=sma_period).mean()
    latest_price = df['close'].iloc[-1]
    latest_sma = df['sma'].iloc[-1]

    # --- Direction prediction (based on SMA) ---
    if latest_price > latest_sma:
        direction = "bullish"
        dir_confidence = "moderate"
    elif latest_price < latest_sma:
        direction = "bearish"
        dir_confidence = "moderate"
    else:
        direction = "neutral"
        dir_confidence = "low"

    # --- Volatility regime (unchanged) ---
    if latest_atr > latest_atr_ma * 1.1:
        regime = "expanding"
    elif latest_atr < latest_atr_ma * 0.9:
        regime = "contracting"
    else:
        regime = "stable"

    # Combine: if strong direction and volatility expanding -> higher confidence
    if regime == "expanding" and percentile > 60:
        vol_note = "Volatility rising."
    elif regime == "contracting" and percentile < 40:
        vol_note = "Volatility falling."
    else:
        vol_note = "Volatility stable or mixed."

    # Final note
    note = f"Direction: {direction} (price {'above' if latest_price > latest_sma else 'below'} SMA{ sma_period}). {vol_note}"

    # Last and first candle
    last = df.iloc[-1]
    first = df.iloc[0]
    price_change = round(latest_price - first['close'], 2)
    price_change_pct = round((price_change / first['close']) * 100, 2)
    avg_volume = round(df['volume'].mean(), 0)
    high_30 = round(df['high'].max(), 2)
    low_30 = round(df['low'].min(), 2)

    result = {
        # Main prediction is now DIRECTION
        "prediction": direction,
        "direction_confidence": dir_confidence,
        "volatility_regime": regime,
        "atr": round(latest_atr, 4),
        "atr_ma_5": round(latest_atr_ma, 4),
        "atr_percentile": round(percentile, 1),
        "sma_20": round(latest_sma, 2),
        "current_price": round(latest_price, 2),
        "price_position": "above" if latest_price > latest_sma else "below" if latest_price < latest_sma else "equal",
        "last_candle_time": f"{last['date']} {last['clock']}",
        "confidence": "high" if (regime == "expanding" and direction != "neutral") else "moderate" if direction != "neutral" else "low",
        "note": note,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candle_count": len(df),
        "atr_period": atr_period,
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

    if len(df) < 20:
        print(f"Warning: only {len(df)} candles. Results may be unreliable.")

    try:
        prediction_meta = predict_next_5_candles(df)
    except Exception as e:
        print(f"Error during prediction: {e}")
        return

    output_file = 'ATR14_prediction_output.json'
    with open(output_file, 'w') as f:
        json.dump(prediction_meta, f, indent=2)

    print(f"✅ Prediction metadata written to {output_file}")
    print(json.dumps(prediction_meta, indent=2))

if __name__ == "__main__":
    main()