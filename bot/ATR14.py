import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone

def compute_atr(df, period=14):
    """
    Compute ATR (Average True Range) for the given OHLCV data.
    df: DataFrame with 'high', 'low', 'close'
    returns: pandas Series of ATR values
    """
    high = df['high']
    low = df['low']
    close = df['close'].shift()
    
    tr1 = high - low
    tr2 = (high - close).abs()
    tr3 = (low - close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def predict_next_5_candles_atr(df, period=14):
    """
    Predict volatility regime for the next 5 candles based on ATR(14).
    Uses:
      - Current ATR
      - 5-period moving average of ATR (to detect expansion/contraction)
      - Percentile rank of current ATR over the last 30 candles
    Returns a dict with prediction metadata.
    """
    if len(df) < period + 5:  # need enough for MA and percentile
        raise ValueError(f"Need at least {period + 5} candles for reliable ATR analysis.")

    df['atr'] = compute_atr(df, period)
    # 5-period MA of ATR
    df['atr_ma'] = df['atr'].rolling(window=5).mean()
    
    latest_atr = df['atr'].iloc[-1]
    latest_atr_ma = df['atr_ma'].iloc[-1]
    
    # Percentile rank of latest ATR over last 30 (or all available)
    lookback = min(30, len(df))
    atr_history = df['atr'].iloc[-lookback:]
    percentile = (atr_history < latest_atr).sum() / len(atr_history) * 100
    
    # Determine volatility regime
    # Rule: if ATR > 1.1 * ATR_MA => expanding, if < 0.9 => contracting
    if latest_atr > latest_atr_ma * 1.1:
        regime = "expanding"
    elif latest_atr < latest_atr_ma * 0.9:
        regime = "contracting"
    else:
        regime = "stable"
    
    # Prediction: if expanding and percentile high -> volatile; if contracting and low -> calm
    if regime == "expanding" and percentile > 60:
        prediction = "volatile"
        confidence = "high" if percentile > 80 else "moderate"
        note = "ATR rising, volatility increasing – expect wider price swings."
    elif regime == "contracting" and percentile < 40:
        prediction = "calm"
        confidence = "high" if percentile < 20 else "moderate"
        note = "ATR falling, volatility decreasing – expect tighter ranges."
    else:
        # mixed signals -> neutral
        prediction = "neutral"
        confidence = "low"
        note = "No clear volatility signal; ATR is stable or mixed."

    # Additional nuance: if percentile is very high regardless of regime
    if percentile > 90:
        note += " ATR near historical highs – market turbulence likely."
    elif percentile < 10:
        note += " ATR near historical lows – potential for a breakout."

    # Last candle info
    last = df.iloc[-1]
    first = df.iloc[0]

    # ==== EXTRA METADATA ====
    latest_price = df['close'].iloc[-1]
    price_change = round(latest_price - first['close'], 2)
    price_change_pct = round((price_change / first['close']) * 100, 2)
    avg_volume = round(df['volume'].mean(), 0)
    high_30 = round(df['high'].max(), 2)
    low_30 = round(df['low'].min(), 2)

    result = {
        # Core prediction
        "prediction": prediction,           # "volatile", "calm", or "neutral"
        "atr": round(latest_atr, 4),
        "atr_ma_5": round(latest_atr_ma, 4),
        "atr_percentile": round(percentile, 1),
        "regime": regime,                   # expanding / contracting / stable
        "current_price": round(latest_price, 2),
        "last_candle_time": f"{last['date']} {last['clock']}",
        "confidence": confidence,
        "note": note,

        # Extended fields
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candle_count": len(df),
        "atr_period": period,
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

    if len(df) < 19:  # at least 14 + 5
        print(f"Warning: only {len(df)} candles provided. ATR analysis may be unreliable.")

    try:
        prediction_meta = predict_next_5_candles_atr(df)
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