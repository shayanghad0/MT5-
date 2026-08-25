# Docs

Research notes and AI-generated references for the trading bots.

## Contents

### deepseek/

AI-generated research on optimal lookback periods for trend analysis on 1-minute candles.

- **Instant.md** - Research on how many candles (`X`) a bot should read to analyze trend for the next 5 candles. Covers the 5x-10x rule, timeframe dependency, dual-lookback strategy, and final recommendations for 1m charts (X=200 candles).
- **Expert.md** - Similar research from a different AI model. Recommends X=20-30 candles for 1m charts, with guidance on backtesting and ensemble lookback approaches.
