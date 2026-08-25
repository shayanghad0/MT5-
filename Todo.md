Here’s a structured **TODO Table** for your 15 indicators, including a clear breakdown of their purpose, category, and a suggested action plan to help you prioritize implementation.

| # | Indicator / Feature | Category | Primary Use / Signal | Suggested TODO Action |
| :---: | :--- | :--- | :--- | :--- |
| **1** | **RSI (14)** | Momentum | Identifies overbought (>70) / oversold (<30) conditions for reversals. | **Code:** Add divergence detection (price vs. RSI). |
| **2** | **EMA (9 & 21)** | Trend | Dynamic support/resistance; short-term trend direction (bullish when 9 > 21). | **Code:** Plot on chart; trigger cross-over alerts. |
| **3** | **MACD (12,26,9)** | Momentum | Histogram slope and signal-line crossovers to detect momentum shifts. | **Code:** Add histogram slope color-coding (green/red). |
| **4** | **Bollinger Bands (%B)** | Volatility / Mean-Reversion | Shows position within bands (0 = lower, 1 = upper) for squeeze/breakout plays. | **Code:** Generate alerts when %B crosses 0.2 or 0.8. |
| **5** | **ATR (14)** | Volatility | Absolute volatility gauge; used to set dynamic stop-losses (e.g., 1.5x ATR). | **Code:** Integrate into position sizing and trailing stop logic. |
| **6** | **Stochastic (%K/%D)** | Momentum | Short-term reversal detection when %K crosses %D in extreme zones (>80 / <20). | **Code:** Filter signals with trend (only buy when uptrend confirmed). |
| **7** | **CCI (20)** | Momentum / Cycle | Measures trend strength; extremes (+100/-100) signal cyclical turning points. | **Code:** Use as a secondary filter for RSI/Stochastic divergence. |
| **8** | **ADX (14)** | Trend Strength | **High ADX (>25)** = strong trend (use trending strategies). **Low (<20)** = ranging (use mean-reversion). | **Code:** Build a regime-switch logic (Trend vs. Range mode). |
| **9** | **OBV (On-Balance Volume)** | Volume | Confirms price moves (price up + OBV up = healthy; divergence = weakness). | **Code:** Plot trendline breaks on OBV for early entry signals. |
| **10** | **VWAP** | Volume / Institutional | "Fair value" for the day; acts as magnetic support/resistance for intraday. | **Code:** Use as a benchmark for entry/exit (buy below VWAP, sell above). |
| **11** | **Fibonacci Retracement** | Support/Resistance | Dynamic levels (0.382, 0.5, 0.618) from recent swing high/low. | **Code:** Automate calculation of recent pivot points to draw zones. |
| **12** | **Ichimoku (Tenkan/Kijun)** | Trend / Crossover | Tenkan (9) crossing Kijun (26) gives trend signals (similar to EMA cross). | **Code:** Add cross-over alerts; combine with "Chikou" span for confirmation. |
| **13** | **Linear Regression Slope (5)** | Trend Velocity | Measures immediate trend steepness and direction (positive/negative slope). | **Code:** Use slope angle to gauge momentum intensity (steep = aggressive). |
| **14** | **Volatility Ratio (ATR/Close)** | Volatility Regime | Normalized volatility percentage; identifies high/low volatility environments. | **Code:** Adjust strategy parameters dynamically (wide stops in high V.R.). |
| **15** | **MFI (Money Flow Index, 14)** | Volume / Momentum | Volume-weighted RSI; filters false RSI signals (e.g., divergence with MFI = strong). | **Code:** Use MFI divergence as a high-conviction reversal trigger. |

