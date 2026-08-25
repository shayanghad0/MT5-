import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone

def compute_adx(df, period=14):
    """
    Compute ADX, +DI, -DI for the given OHLCV data.
    Returns DataFrame with columns: 'adx', 'plus_di', 'minus_di'
    """
    high = df['high']
    low = df['low']
    close = df['close']

    # True Range
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()

    # Directional Movement
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > 0) & (up_move > down_move), 0)
    minus_dm = down_move.where((down_move > 0) & (down_move > up_move), 0)

    # Smoothed DM and ATR
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr.replace(0, 1e-9))
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr.replace(0, 1e-9))

    # DX = |+DI - -DI| / (+DI + -DI) * 100
    dx = 100 * (np.abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, 1e-9))
    adx = dx.rolling(window=period).mean()

    df['plus_di'] = plus_di
    df['minus_di'] = minus_di
    df['adx'] = adx
    return df

def predict_next_5_candles_adx(df, adx_period=14, sma_period=20):
    """
    Predict direction for the next 5 candles based on ADX(14) and +DI/-DI.
    Uses ADX strength to confirm trend:
      - ADX > 25: strong trend, follow +DI/-DI crossover
      - ADX < 25: weak trend, use SMA(20) as tie-breaker
    Always returns bullish or bearish (no neutral).
    """
    min_period = max(adx_period, sma_period) + 5
    if len(df) < min_period:
        raise ValueError(f"Need at least {min_period} candles for ADX.")

    df = compute_adx(df, adx_period)
    df['sma'] = df['close'].rolling(window=sma_period).mean()

    latest_adx = df['adx'].iloc[-1]
    latest_plus = df['plus_di'].iloc[-1]
    latest_minus = df['minus_di'].iloc[-1]
    latest_price = df['close'].iloc[-1]
    latest_sma = df['sma'].iloc[-1]

    # Determine which DI is higher
    if latest_plus > latest_minus:
        di_bias = "bullish"
    elif latest_minus > latest_plus:
        di_bias = "bearish"
    else:
        di_bias = "neutral"

    # ---- Prediction logic ----
    # 1. Strong trend (ADX > 25): follow DI bias
    if latest_adx > 25:
        if di_bias == "bullish":
            prediction = "bullish"
            confidence = "high" if latest_adx > 40 else "moderate"
            note = f"Strong trend (ADX={latest_adx:.1f}), +DI > -DI – bullish."
        elif di_bias == "bearish":
            prediction = "bearish"
            confidence = "high" if latest_adx > 40 else "moderate"
            note = f"Strong trend (ADX={latest_adx:.1f}), -DI > +DI – bearish."
        else:
            # DI equal, fallback to SMA
            prediction = "bullish" if latest_price > latest_sma else "bearish"
            confidence = "low"
            note = f"Strong ADX but DI equal, using SMA trend."
    else:
        # 2. Weak/Ranging (ADX <= 25): use SMA trend
        if latest_price > latest_sma:
            prediction = "bullish"
            confidence = "low"
            note = f"Weak trend (ADX={latest_adx:.1f}), price above SMA – mild bullish."
        else:
            prediction = "bearish"
            confidence = "low"
            note = f"Weak trend (ADX={latest_adx:.1f}), price below SMA – mild bearish."

        # If ADX is extremely low (< 15), we might still trust DI bias if clear
        if latest_adx < 15 and abs(latest_plus - latest_minus) > 10:
            # If DI difference is large, follow it even if ADX weak
            if latest_plus > latest_minus:
                prediction = "bullish"
                confidence = "moderate"
                note = f"Very weak ADX but strong DI divergence (+DI > -DI) – bullish bias."
            else:
                prediction = "bearish"
                confidence = "moderate"
                note = f"Very weak ADX but strong DI divergence (-DI > +DI) – bearish bias."

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
        "adx": round(latest_adx, 2),
        "plus_di": round(latest_plus, 2),
        "minus_di": round(latest_minus, 2),
        "di_bias": di_bias,
        "sma_20": round(latest_sma, 2),
        "current_price": round(latest_price, 2),
        "last_candle_time": f"{last['date']} {last['clock']}",
        "confidence": confidence,
        "note": note,

        # Extended fields
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candle_count": len(df),
        "adx_period": adx_period,
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
        print(f"Warning: only {len(df)} candles provided. ADX may be unreliable.")

    try:
        prediction_meta = predict_next_5_candles_adx(df)
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