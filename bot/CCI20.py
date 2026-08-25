import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone

def predict_next_5_candles_cci(df, cci_period=20, sma_period=20):
    """
    Predict direction for the next 5 candles based on CCI(20).
    Always returns bullish or bearish (no neutral) using:
      - CCI > 100 -> overbought -> bearish (mean reversion)
      - CCI < -100 -> oversold -> bullish (mean reversion)
      - Between -100 and +100: use price vs SMA(20) for trend
      - CCI slope (last 5 periods) adjusts confidence
    Returns a dict with prediction metadata.
    """
    min_period = max(cci_period, sma_period) + 5
    if len(df) < min_period:
        raise ValueError(f"Need at least {min_period} candles for CCI.")

    # ---- CCI calculation ----
    df['tp'] = (df['high'] + df['low'] + df['close']) / 3
    df['tp_mean'] = df['tp'].rolling(window=cci_period).mean()
    # Mean absolute deviation (MAD)
    df['tp_mad'] = df['tp'].rolling(window=cci_period).apply(
        lambda x: np.abs(x - x.mean()).mean(), raw=True
    )
    # Avoid division by zero
    df['tp_mad'] = df['tp_mad'].replace(0, 1e-9)
    df['cci'] = (df['tp'] - df['tp_mean']) / (0.015 * df['tp_mad'])

    # ---- Trend filter ----
    df['sma'] = df['close'].rolling(window=sma_period).mean()

    # ---- CCI slope (last 5 periods) ----
    def calc_slope(series):
        if len(series) < 5:
            return 0.0
        x = np.arange(len(series))
        return np.polyfit(x, series, 1)[0]

    df['cci_slope'] = df['cci'].rolling(5).apply(calc_slope, raw=True)

    latest_price = df['close'].iloc[-1]
    latest_sma = df['sma'].iloc[-1]
    latest_cci = df['cci'].iloc[-1]
    latest_slope = df['cci_slope'].iloc[-1]
    trend_bullish = latest_price > latest_sma

    # ---- Prediction logic ----
    # 1. Extreme overbought (>100) -> bearish
    if latest_cci > 100:
        prediction = "bearish"
        confidence = "high" if latest_cci > 150 else "moderate"
        note = f"Overbought (CCI={latest_cci:.1f}) – mean reversion down likely."

    # 2. Extreme oversold (<-100) -> bullish, but check trend
    elif latest_cci < -100:
        if trend_bullish or latest_cci < -150:
            prediction = "bullish"
            confidence = "high" if latest_cci < -150 else "moderate"
            note = f"Oversold (CCI={latest_cci:.1f}) – mean reversion up likely."
        else:
            # Oversold but in bearish trend – stay bearish
            prediction = "bearish"
            confidence = "low"
            note = f"Oversold (CCI={latest_cci:.1f}) but price below SMA – downtrend persists."

    # 3. Neutral zone (-100 to +100) – use trend + slope
    else:
        if trend_bullish:
            base = "bullish"
        else:
            base = "bearish"
        
        # Adjust confidence with slope: if slope agrees, confidence higher
        if (base == "bullish" and latest_slope > 0) or (base == "bearish" and latest_slope < 0):
            confidence = "moderate"
        else:
            confidence = "low"
        
        prediction = base
        note = f"CCI neutral ({latest_cci:.1f}) with {base} trend (slope: {'rising' if latest_slope > 0 else 'falling'})."

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
        "cci": round(latest_cci, 2),
        "cci_slope": round(latest_slope, 2),
        "sma_20": round(latest_sma, 2),
        "current_price": round(latest_price, 2),
        "trend": "bullish" if trend_bullish else "bearish",
        "last_candle_time": f"{last['date']} {last['clock']}",
        "confidence": confidence,
        "note": note,

        # Extended fields
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candle_count": len(df),
        "cci_period": cci_period,
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
        print(f"Warning: only {len(df)} candles provided. CCI may be unreliable.")

    try:
        prediction_meta = predict_next_5_candles_cci(df)
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