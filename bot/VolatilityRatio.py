import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone

def compute_atr(df, period=14):
    """
    Compute Average True Range (ATR) for the given OHLCV data.
    Returns pandas Series of ATR values.
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

def predict_next_5_candles_vr(df, atr_period=14, lookback=10, sma_period=20):
    """
    Predict direction for the next 5 candles based on Volatility Ratio (ATR/Close).
    Uses:
      - Volatility Ratio = ATR(14) / Close
      - Current ratio compared to its 10-period moving average:
          * > 1.2 * average => high volatility
          * < 0.8 * average => low volatility
          * else neutral volatility
      - Direction based on SMA(20) trend
      - Confidence: high if volatility is high and trend is clear, else moderate/low.
    Always returns bullish or bearish (no neutral) with confidence adjustment.
    """
    if len(df) < max(atr_period, lookback, sma_period) + 1:
        raise ValueError(f"Need at least {max(atr_period, lookback, sma_period)} candles.")

    # ---- ATR ----
    df['atr'] = compute_atr(df, atr_period)
    # ---- Volatility Ratio ----
    df['vol_ratio'] = df['atr'] / df['close']
    # ---- Rolling average of volatility ratio (10 periods) ----
    df['vr_ma'] = df['vol_ratio'].rolling(window=lookback).mean()
    # ---- Trend filter ----
    df['sma'] = df['close'].rolling(window=sma_period).mean()

    latest_price = df['close'].iloc[-1]
    latest_vr = df['vol_ratio'].iloc[-1]
    latest_vr_ma = df['vr_ma'].iloc[-1]
    latest_sma = df['sma'].iloc[-1]

    # ---- Determine volatility regime ----
    if latest_vr > 1.2 * latest_vr_ma:
        regime = "high"
    elif latest_vr < 0.8 * latest_vr_ma:
        regime = "low"
    else:
        regime = "neutral"

    # ---- Direction from SMA trend ----
    if latest_price > latest_sma:
        direction = "bullish"
    else:
        direction = "bearish"

    # ---- Confidence based on volatility regime ----
    if regime == "high":
        confidence = "high"
        note = f"High volatility (VR={latest_vr:.4f}), {direction} trend – strong momentum expected."
    elif regime == "low":
        confidence = "low"
        note = f"Low volatility (VR={latest_vr:.4f}), {direction} trend – weak momentum, ranging likely."
    else:  # neutral
        confidence = "moderate"
        note = f"Normal volatility (VR={latest_vr:.4f}), {direction} trend."

    # ---- Additional note for extreme volatility spikes ----
    if latest_vr > 2.0 * latest_vr_ma:
        note += " Extreme volatility spike – caution advised."

    # ---- Percentile rank of current VR over last 30 periods ----
    vr_history = df['vol_ratio'].tail(30)
    percentile = (vr_history < latest_vr).sum() / len(vr_history) * 100 if len(vr_history) > 0 else 50

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
        "prediction": direction,
        "volatility_ratio": round(latest_vr, 4),
        "vr_ma_10": round(latest_vr_ma, 4),
        "volatility_regime": regime,
        "vr_percentile": round(percentile, 1),
        "sma_20": round(latest_sma, 2),
        "current_price": round(latest_price, 2),
        "last_candle_time": f"{last['date']} {last['clock']}",
        "confidence": confidence,
        "note": note,

        # Extended fields
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candle_count": len(df),
        "atr_period": atr_period,
        "vr_lookback": lookback,
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
        print(f"Warning: only {len(df)} candles provided. Volatility Ratio may be unreliable.")

    try:
        prediction_meta = predict_next_5_candles_vr(df)
    except Exception as e:
        print(f"Error during prediction: {e}")
        return

    output_file = 'VolatilityRatio_prediction_output.json'
    with open(output_file, 'w') as f:
        json.dump(prediction_meta, f, indent=2)

    print(f"✅ Prediction metadata written to {output_file}")
    print(json.dumps(prediction_meta, indent=2))

if __name__ == "__main__":
    main()