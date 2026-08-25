import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone

def compute_mfi(df, period=14):
    """
    Compute Money Flow Index (MFI) for the given OHLCV data.
    Returns pandas Series of MFI values.
    """
    # Typical Price
    df['tp'] = (df['high'] + df['low'] + df['close']) / 3
    # Money Flow = TP * Volume
    df['mf'] = df['tp'] * df['volume']
    # Positive and negative money flow
    df['mf_pos'] = df['mf'].where(df['tp'] > df['tp'].shift(), 0)
    df['mf_neg'] = df['mf'].where(df['tp'] < df['tp'].shift(), 0)
    # Sum over period
    df['mf_pos_sum'] = df['mf_pos'].rolling(window=period).sum()
    df['mf_neg_sum'] = df['mf_neg'].rolling(window=period).sum()
    # Money Flow Ratio
    ratio = df['mf_pos_sum'] / df['mf_neg_sum'].replace(0, 1e-9)
    # MFI
    mfi = 100 - (100 / (1 + ratio))
    return mfi

def predict_next_5_candles_mfi(df, mfi_period=14, sma_period=20):
    """
    Predict direction for the next 5 candles based on MFI(14).
    Uses:
      - MFI > 80 => overbought => bearish
      - MFI < 20 => oversold => bullish, but overridden by trend if not extreme
      - Between 20-80 => use SMA(20) trend
      - Confidence: high if extreme MFI (<10 or >90) or if MFI and trend agree
    Always returns bullish or bearish (no neutral).
    """
    if len(df) < max(mfi_period, sma_period) + 1:
        raise ValueError(f"Need at least {max(mfi_period, sma_period)} candles.")

    # Compute MFI
    df['mfi'] = compute_mfi(df, mfi_period)
    # Trend filter
    df['sma'] = df['close'].rolling(window=sma_period).mean()

    latest_price = df['close'].iloc[-1]
    latest_mfi = df['mfi'].iloc[-1]
    latest_sma = df['sma'].iloc[-1]
    trend_bullish = latest_price > latest_sma

    # MFI slope (last 3 periods) for confidence adjustment
    if len(df) >= 3:
        prev_mfi = df['mfi'].iloc[-2] if len(df) >= 2 else latest_mfi
        mfi_change = latest_mfi - prev_mfi
    else:
        mfi_change = 0

    # ---- Prediction logic ----
    # 1. Overbought (>80) -> bearish
    if latest_mfi > 80:
        prediction = "bearish"
        confidence = "high" if latest_mfi > 90 else "moderate"
        note = f"Overbought (MFI={latest_mfi:.1f}) – bearish reversal likely."

    # 2. Oversold (<20) – bullish but check trend
    elif latest_mfi < 20:
        if latest_mfi < 10:
            # Extreme oversold overrides trend
            prediction = "bullish"
            confidence = "high"
            note = f"Extreme oversold (MFI={latest_mfi:.1f}) – strong bounce potential."
        elif trend_bullish:
            prediction = "bullish"
            confidence = "moderate"
            note = f"Oversold (MFI={latest_mfi:.1f}) with bullish trend – bounce likely."
        else:
            # Oversold but in downtrend – stay bearish
            prediction = "bearish"
            confidence = "low"
            note = f"Oversold (MFI={latest_mfi:.1f}) but price below SMA – downtrend persists."

    # 3. Neutral zone (20-80) – use SMA trend
    else:
        if trend_bullish:
            prediction = "bullish"
            confidence = "low"
            note = f"MFI neutral ({latest_mfi:.1f}) with bullish trend."
        else:
            prediction = "bearish"
            confidence = "low"
            note = f"MFI neutral ({latest_mfi:.1f}) with bearish trend."

        # If MFI is near edges (30-40 or 60-70) and slope agrees, raise confidence
        if 30 <= latest_mfi <= 40 and trend_bullish and mfi_change > 0:
            confidence = "moderate"
            note = f"MFI rising from lower zone with bullish trend."
        elif 60 <= latest_mfi <= 70 and not trend_bullish and mfi_change < 0:
            confidence = "moderate"
            note = f"MFI falling from upper zone with bearish trend."

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
        "mfi": round(latest_mfi, 2),
        "mfi_change": round(mfi_change, 2),
        "sma_20": round(latest_sma, 2),
        "current_price": round(latest_price, 2),
        "last_candle_time": f"{last['date']} {last['clock']}",
        "confidence": confidence,
        "note": note,

        # Extended fields
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candle_count": len(df),
        "mfi_period": mfi_period,
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
        print(f"Warning: only {len(df)} candles provided. MFI may be unreliable.")

    try:
        prediction_meta = predict_next_5_candles_mfi(df)
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