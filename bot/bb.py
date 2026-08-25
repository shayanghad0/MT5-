import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone

def predict_next_5_candles_bb(df, period=20, num_std=2, sma_period=20):
    """
    Predict direction for the next 5 candles based on Bollinger Bands %B and SMA trend.
    Uses:
      - %B = (close - lower) / (upper - lower)
      - Extreme %B (<0 or >1) -> mean‑reversion (bullish/bearish)
      - Inside bands: if %B near edges (<0.2 or >0.8) use that, else use SMA trend.
      - SMA(20) trend: price above SMA -> bullish, below -> bearish.
    Returns a dict with prediction metadata.
    """
    if len(df) < max(period, sma_period):
        raise ValueError(f"Need at least {max(period, sma_period)} candles.")

    # Bollinger Bands
    df['sma'] = df['close'].rolling(window=period).mean()
    df['std'] = df['close'].rolling(window=period).std()
    df['upper'] = df['sma'] + (df['std'] * num_std)
    df['lower'] = df['sma'] - (df['std'] * num_std)
    denominator = df['upper'] - df['lower']
    denominator[denominator == 0] = 1e-9
    df['pct_b'] = (df['close'] - df['lower']) / denominator

    # Additional SMA(20) for trend
    df['sma_trend'] = df['close'].rolling(window=sma_period).mean()

    latest_price = df['close'].iloc[-1]
    latest_pct_b = df['pct_b'].iloc[-1]
    latest_upper = df['upper'].iloc[-1]
    latest_lower = df['lower'].iloc[-1]
    latest_sma = df['sma'].iloc[-1]
    latest_sma_trend = df['sma_trend'].iloc[-1]

    # Band position
    if latest_pct_b < 0:
        band_position = "below_lower"
    elif latest_pct_b > 1:
        band_position = "above_upper"
    else:
        band_position = "inside"

    # ==== PREDICTION LOGIC (BB %B + SMA trend) ====
    # 1. Extreme %B – mean‑reversion
    if latest_pct_b < 0:
        prediction = "bullish"
        confidence = "high" if latest_pct_b < -0.1 else "moderate"
        note = "Price below lower band – oversold, mean-reversion up likely."
    elif latest_pct_b > 1:
        prediction = "bearish"
        confidence = "high" if latest_pct_b > 1.1 else "moderate"
        note = "Price above upper band – overbought, mean-reversion down likely."
    else:
        # 2. Inside bands: check proximity to edges
        if latest_pct_b < 0.2:
            prediction = "bullish"
            confidence = "moderate"
            note = "Price near lower band – potential bounce."
        elif latest_pct_b > 0.8:
            prediction = "bearish"
            confidence = "moderate"
            note = "Price near upper band – potential pullback."
        else:
            # 3. Neutral zone: use SMA(20) trend
            if latest_price > latest_sma_trend:
                prediction = "bullish"
                confidence = "low"
                note = "Price in middle of bands but above SMA – mild bullish bias."
            elif latest_price < latest_sma_trend:
                prediction = "bearish"
                confidence = "low"
                note = "Price in middle of bands but below SMA – mild bearish bias."
            else:
                prediction = "neutral"
                confidence = "low"
                note = "Price in middle of bands and at SMA – no clear signal."

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
        "pct_b": round(latest_pct_b, 4),
        "current_price": round(latest_price, 2),
        "upper_band": round(latest_upper, 2),
        "middle_band": round(latest_sma, 2),
        "lower_band": round(latest_lower, 2),
        "band_position": band_position,
        "sma_trend": round(latest_sma_trend, 2),
        "last_candle_time": f"{last['date']} {last['clock']}",
        "confidence": confidence,
        "note": note,

        # Extended fields
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candle_count": len(df),
        "bb_period": period,
        "bb_std": num_std,
        "sma_trend_period": sma_period,
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
        print(f"Warning: only {len(df)} candles provided. Bollinger Bands may be unreliable.")

    try:
        prediction_meta = predict_next_5_candles_bb(df)
    except Exception as e:
        print(f"Error during prediction: {e}")
        return

    output_file = 'BB_prediction_output.json'
    with open(output_file, 'w') as f:
        json.dump(prediction_meta, f, indent=2)

    print(f"✅ Prediction metadata written to {output_file}")
    print(json.dumps(prediction_meta, indent=2))

if __name__ == "__main__":
    main()