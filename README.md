# MT5 Trading Bots

MetaTrader 5 trading bot workspace. Exports candle data from MT5 and runs technical indicator bots to predict the next 5 candle directions.

## Structure

```
bot/          - Trading bots and data exporters
docs/         - Research notes and AI-generated references
```

## Bots

| Bot | File | Indicator | Description |
|-----|------|-----------|-------------|
| Export | `bot/export.py` | - | Exports last 30 completed 1m candles from MT5 to `candles.json`. Run this first to get data for other bots. |
| RSI14 | `bot/RSI14.py` | RSI(14) + EMA(9) | Predicts direction using RSI overbought/oversold levels combined with EMA(9) trend confirmation. |
| EMA9 | `bot/EMA9.py` | EMA(9) | Predicts direction based on price position relative to EMA(9) and EMA slope. |
| EMA21 | `bot/EMA21.py` | EMA(21) | Predicts direction based on price position relative to EMA(21) and EMA slope over last 5 periods. |
| Bollinger Bands | `bot/bb.py` | BB %B + SMA(20) | Predicts direction using Bollinger Bands %B (mean-reversion) and SMA(20) trend for neutral zones. |
| ATR14 | `bot/ATR14.py` | SMA(20) + ATR(14) | Predicts direction using SMA(20) trend and reports ATR(14) volatility regime (expanding/contracting/stable). |

## Quick Start

```bash
# Step 1: Export last 30 1m candles from MT5
python bot/export.py SYMBOL

# Step 2: Run any prediction bot (reads candles.json)
python bot/RSI14.py
python bot/EMA9.py
python bot/EMA21.py
python bot/bb.py
python bot/ATR14.py
```

All bots read `candles.json` and output results to `prediction_output.json`.
