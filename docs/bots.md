> [!WARNING]
> AI-generated, for reference only. I dont accept it for Reject it 

**Critical Caveat:** With only 30 candles, traditional Machine Learning (LSTM/XGBoost) will severely overfit. Therefore, this code uses a **Weighted Ensemble Scoring System** combining momentum, oscillators, and volatility. It extrapolates the current 5-candle trajectory and adjusts the score using mean-reversion signals (RSI/BB) and trend strength (ADX). This gives a statistically reasonable "best guess" for the immediate short-term direction.

---

## Table of Contents

1. [Export Script](#1-export-script)
2. [ADX Bot](#2-adx-bot)
3. [ATR14 Bot](#3-atr14-bot)
4. [Bollinger Bands Bot](#4-bollinger-bands-bot)
5. [CCI20 Bot](#5-cci20-bot)
6. [EMA9 Bot](#6-ema9-bot)
7. [EMA21 Bot](#7-ema21-bot)
8. [Fibonacci Bot](#8-fibonacci-bot)
9. [Ichimoku Bot](#9-ichimoku-bot)
10. [LinearRegression Bot](#10-linearregression-bot)
11. [MACD Bot](#11-macd-bot)
12. [MFI Bot](#12-mfi-bot)
13. [OBV Bot](#13-obv-bot)
14. [RSI14 Bot](#14-rsi14-bot)
15. [Stochastic Bot](#15-stochastic-bot)
16. [VolatilityRatio Bot](#16-volatilityratio-bot)
17. [VWAP Bot](#17-vwap-bot)

---

## Common Architecture

All bots share the same structure:

- **Input:** Reads `candles.json` (OHLCV data with `date`, `clock`, `open`, `high`, `low`, `close`, `volume`)
- **Output:** Writes `prediction_output.json` with prediction metadata
- **Prediction:** Always `bullish` or `bearish` (some support `neutral`)
- **Confidence:** `high`, `moderate`, or `low`
- **Extended fields:** Timestamp, candle count, price change over 30 candles, volume stats, 30-period high/low

---

## 1. Export Script

**File:** `export.py`

**Purpose:** Fetches the last 30 completed 1-minute candles from MetaTrader 5 and saves them to `candles.json`.

**Usage:**
```bash
python export.py [SYMBOL]
# Example: python export.py XAUUSD
# If no symbol provided, prompts interactively
```

**Output format:**
```json
{
  "date": "2026-08-25",
  "clock": "14:23:45",
  "timezone": "+00:00",
  "open": 1234.56,
  "high": 1234.78,
  "low": 1234.12,
  "close": 1234.34,
  "volume": 156
}
```

**Dependencies:** `MetaTrader5` Python package, MT5 must be running.

---

## 2. ADX Bot

**File:** `ADX.py`

**Indicator:** Average Directional Index (14-period) + SMA(20)

**Logic:**
| ADX Value | DI Bias | Prediction | Confidence |
|-----------|---------|------------|------------|
| ADX > 25 | +DI > -DI | bullish | high (ADX>40) / moderate |
| ADX > 25 | -DI > +DI | bearish | high (ADX>40) / moderate |
| ADX > 25 | Equal | SMA-based | low |
| ADX ≤ 25 | Any | SMA-based | low |
| ADX < 15 | DI diff > 10 | DI-biased | moderate |

**Output fields:** `prediction`, `adx`, `plus_di`, `minus_di`, `di_bias`, `sma_20`, `current_price`, `confidence`, `note`

---

## 3. ATR14 Bot

**File:** `ATR14.py`

**Indicator:** Average True Range (14-period) + SMA(20)

**Logic:**
- Direction: Price > SMA(20) → bullish, Price < SMA(20) → bearish
- Volatility regime: ATR vs 5-period ATR moving average
  - ATR > 1.1× MA → expanding
  - ATR < 0.9× MA → contracting
  - else → stable
- Confidence: high if expanding + directional, moderate if directional, low if neutral

**Output fields:** `prediction`, `direction_confidence`, `volatility_regime`, `atr`, `atr_ma_5`, `atr_percentile`, `sma_20`, `current_price`, `price_position`, `confidence`, `note`

---

## 4. Bollinger Bands Bot

**File:** `bb.py`

**Indicator:** Bollinger Bands (20-period, 2σ) + SMA(20) trend

**Logic:**
| %B Position | Condition | Prediction | Confidence |
|-------------|-----------|------------|------------|
| %B < 0 | Below lower band | bullish | high (<-0.1) / moderate |
| %B > 1 | Above upper band | bearish | high (>1.1) / moderate |
| 0 < %B < 0.2 | Near lower band | bullish | moderate |
| 0.8 < %B < 1 | Near upper band | bearish | moderate |
| 0.2–0.8 | Middle | SMA-based | low |

**Output fields:** `prediction`, `pct_b`, `upper_band`, `middle_band`, `lower_band`, `band_position`, `sma_trend`, `current_price`, `confidence`, `note`

---

## 5. CCI20 Bot

**File:** `CCI20.py`

**Indicator:** Commodity Channel Index (20-period) + SMA(20) + CCI slope

**Logic:**
| CCI Range | Condition | Prediction | Confidence |
|-----------|-----------|------------|------------|
| CCI > 100 | Overbought | bearish | high (>150) / moderate |
| CCI < -100 | Oversold + bullish trend | bullish | high (<-150) / moderate |
| CCI < -100 | Oversold + bearish trend | bearish | low |
| -100 to 100 | Neutral | SMA-based | low/moderate (slope-adjusted) |

**Output fields:** `prediction`, `cci`, `cci_slope`, `sma_20`, `current_price`, `trend`, `confidence`, `note`

---

## 6. EMA9 Bot

**File:** `EMA9.py`

**Indicator:** Exponential Moving Average (9-period)

**Logic:**
- Price > EMA(9) → bullish (high confidence if EMA rising, moderate if flat/falling)
- Price < EMA(9) → bearish (high confidence if EMA falling, moderate if flat/rising)
- Price = EMA(9) → neutral
- Slope computed over last 3 periods

**Output fields:** `prediction`, `ema_9`, `current_price`, `price_position`, `ema_slope`, `confidence`, `note`

---

## 7. EMA21 Bot

**File:** `EMA21.py`

**Indicator:** Exponential Moving Average (21-period)

**Logic:** Same as EMA9 but with 21-period span and 5-period slope lookback.

**Output fields:** `prediction`, `ema_21`, `current_price`, `price_position`, `ema_slope`, `slope_lookback`, `confidence`, `note`

---

## 8. Fibonacci Bot

**File:** `Fibonacci.py`

**Indicator:** Fibonacci Retracement Levels (30-candle lookback) + SMA(20)

**Levels:** 0.0 (swing low), 0.236, 0.382, 0.5, 0.618, 0.786, 1.0 (swing high)

**Logic:**
| Price Position | Nearest Level | Prediction | Confidence |
|----------------|---------------|------------|------------|
| Above 0.5 | 0.236 or 0.382 | bullish | high |
| Below 0.5 | 0.618 or 0.786 | bearish | high |
| Above 0.5 | 0.618 or 0.786 | bullish | moderate |
| Below 0.5 | 0.236 or 0.382 | bearish | moderate |
| Near 0.5 | Any | SMA-based | low |

**Output fields:** `prediction`, `fib_levels`, `nearest_fib_level`, `nearest_fib_value`, `distance_to_nearest_pct`, `swing_high`, `swing_low`, `sma_20`, `current_price`, `confidence`, `note`

---

## 9. Ichimoku Bot

**File:** `Ichimoku.py`

**Indicator:** Ichimoku Tenkan-sen (9) / Kijun-sen (26) + SMA(20)

**Logic:**
| Crossover | Position | Prediction | Confidence |
|-----------|----------|------------|------------|
| Bullish cross | Tenkan > Kijun | bullish | high |
| Bearish cross | Tenkan < Kijun | bearish | high |
| None | Tenkan above Kijun + price > SMA | bullish | moderate |
| None | Tenkan below Kijun + price < SMA | bearish | moderate |
| None | Equal | SMA-based | low |

**Output fields:** `prediction`, `tenkan`, `kijun`, `crossover`, `position`, `sma_20`, `current_price`, `confidence`, `note`

---

## 10. LinearRegression Bot

**File:** `LinearRegression.py`

**Indicator:** Linear Regression Slope (5-period) + SMA(20)

**Logic:**
- Slope > 0.1% of price → bullish (high if >0.5%, moderate if >0.2%, low if <0.2%)
- Slope < -0.1% of price → bearish (same confidence tiers)
- Slope near zero → SMA-based tie-breaker

**Output fields:** `prediction`, `lr_slope`, `slope_direction`, `sma_20`, `current_price`, `confidence`, `note`

---

## 11. MACD Bot

**File:** `MACD.py`

**Indicator:** MACD (12, 26, 9) histogram + slope

**Logic:**
- Histogram > 0 → bullish
- Histogram < 0 → bearish
- Confidence: high if slope agrees with position (rising positive / falling negative), low if diverging

**Output fields:** `prediction`, `macd_hist`, `macd_line`, `signal_line`, `hist_slope`, `hist_position`, `current_price`, `confidence`, `note`

---

## 12. MFI Bot

**File:** `MFI.py`

**Indicator:** Money Flow Index (14-period) + SMA(20)

**Logic:**
| MFI Range | Condition | Prediction | Confidence |
|-----------|-----------|------------|------------|
| MFI > 80 | Overbought | bearish | high (>90) / moderate |
| MFI < 20 | Extreme oversold (<10) | bullish | high |
| MFI < 20 | Oversold + bullish trend | bullish | moderate |
| MFI < 20 | Oversold + bearish trend | bearish | low |
| 20–80 | Neutral | SMA-based | low (moderate if slope+ trend agree at edges) |

**Output fields:** `prediction`, `mfi`, `mfi_change`, `sma_20`, `current_price`, `confidence`, `note`

---

## 13. OBV Bot

**File:** `OBV.py`

**Indicator:** On-Balance Volume (slope over 5 periods) + SMA(20) trend

**Logic:**
| Condition | Prediction | Confidence |
|-----------|------------|------------|
| Bullish divergence (price down, OBV up) | bullish | high |
| Bearish divergence (price up, OBV down) | bearish | high |
| Trend + OBV slope agree | Trend direction | moderate |
| OBV flat | SMA-based | low |
| Trend + OBV disagree | Price trend | low |

**Output fields:** `prediction`, `obv`, `obv_slope`, `obv_trend`, `divergence`, `sma_20`, `current_price`, `confidence`, `note`

---

## 14. RSI14 Bot

**File:** `RSI14.py`

**Indicator:** Relative Strength Index (14-period) + EMA(9)

**Logic:**
| RSI Range | Condition | Prediction | Confidence |
|-----------|-----------|------------|------------|
| RSI < 30 | Oversold | bullish | high (<25) / moderate |
| RSI > 70 | Overbought | bearish | high (>75) / moderate |
| 30–70 | Neutral | EMA(9)-based | low |

**Output fields:** `prediction`, `rsi`, `rsi_status`, `current_price`, `ema_9`, `confidence`, `note`

---

## 15. Stochastic Bot

**File:** `Stochastic.py`

**Indicator:** Stochastic Oscillator (%K 14, %D 3, smooth 3) + SMA(20)

**Logic:**
| %K Range | Crossover | Trend | Prediction | Confidence |
|----------|-----------|-------|------------|------------|
| > 80 | Any | Any | bearish | high (>90) / moderate |
| < 20 | Any | Extreme (<10) | bullish | high |
| < 20 | Any | Bullish | bullish | moderate |
| < 20 | Any | Bearish | bearish | low |
| 20–80 | Bullish cross | Bullish | bullish | moderate |
| 20–80 | Bullish cross | Bearish | bearish | low (fakeout) |
| 20–80 | Bearish cross | Any | bearish | moderate/low |
| 20–80 | None | Trend-based | Trend direction | low |

**Output fields:** `prediction`, `stoch_k`, `stoch_d`, `crossover`, `sma_20`, `trend`, `current_price`, `confidence`, `note`

---

## 16. VolatilityRatio Bot

**File:** `VolatilityRatio.py`

**Indicator:** Volatility Ratio (ATR/Close) + SMA(20)

**Logic:**
- VR > 1.2× 10-period MA → high volatility → confidence: high
- VR < 0.8× MA → low volatility → confidence: low
- Else → neutral → confidence: moderate
- Direction: SMA(20) trend-based
- Extreme spike (>2× MA) adds caution note

**Output fields:** `prediction`, `volatility_ratio`, `vr_ma_10`, `volatility_regime`, `vr_percentile`, `sma_20`, `current_price`, `confidence`, `note`

---

## 17. VWAP Bot

**File:** `VWAP.py`

**Indicator:** Volume Weighted Average Price (cumulative) + SMA(20)

**Logic:**
| Price Position | VWAP Slope | Prediction | Confidence |
|----------------|------------|------------|------------|
| Above VWAP | Rising | bullish | high |
| Above VWAP | Flat/Falling | bullish | moderate |
| Below VWAP | Falling | bearish | high |
| Below VWAP | Flat/Rising | bearish | moderate |
| Near VWAP (<0.5%) | Any | SMA-based | low |

**Output fields:** `prediction`, `vwap`, `vwap_slope`, `sma_20`, `current_price`, `price_vwap_diff_pct`, `confidence`, `note`

---

## 15 Suggested Indicators & Features to Add

1. **RSI (14)** – Momentum oscillator to spot overbought/oversold conditions. 
2. **EMA (9 & 21)** – Trend direction and dynamic support/resistance.
3. **MACD (12,26,9)** – Histogram slope to detect momentum shifts.
4. **Bollinger Bands (%B)** – Position within volatility bands for mean-reversion signals.
5. **ATR (14)** – Volatility gauge for stop-loss and market turbulence.
6. **Stochastic Oscillator (%K/%D)** – Short-term reversal detection.
7. **CCI (20)** – Trend strength and cyclical turning points.
8. **ADX (14)** – Trend strength filter (high ADX = strong trend, low = ranging).
9. **OBV (On-Balance Volume)** – Volume momentum confirming price moves.
10. **VWAP** – Volume-weighted average price to gauge institutional "fair value".
11. **Fibonacci Retracement Levels** – Dynamic support/resistance from recent swing high/low.
12. **Ichimoku Components (Tenkan/Kijun)** – Crossover signals for trend following.
13. **Linear Regression Slope (5-period)** – Velocity/direction of the immediate trend.
14. **Volatility Ratio (ATR / Close)** – Normalized volatility regime detection.
15. **MFI (Money Flow Index, 14)** – Volume-weighted RSI to filter false signals.
