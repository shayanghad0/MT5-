**⚠️ Critical Caveat:** With only 30 candles, traditional Machine Learning (LSTM/XGBoost) will severely overfit. Therefore, this code uses a **Weighted Ensemble Scoring System** combining momentum, oscillators, and volatility. It extrapolates the current 5-candle trajectory and adjusts the score using mean-reversion signals (RSI/BB) and trend strength (ADX). This gives a statistically reasonable "best guess" for the immediate short-term direction.

---

### 15 Suggested Indicators & Features to Add

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