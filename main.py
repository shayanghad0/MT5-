import subprocess
import sys
import json
import os

SYMBOL = "XAUUSD"
BOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot")
CANDLES_PATH = os.path.join(BOT_DIR, "candles.json")
OUTPUT_PATH = os.path.join(BOT_DIR, "prediction_output.json")

BOTS = [
    "ADX.py",
    "ATR14.py",
    "bb.py",
    "CCI20.py",
    "EMA9.py",
    "EMA21.py",
    "Fibonacci.py",
    "Ichimoku.py",
    "LinearRegression.py",
    "MACD.py",
    "MFI.py",
    "OBV.py",
    "RSI14.py",
    "Stochastic.py",
    "VolatilityRatio.py",
    "VWAP.py",
]


def run_export():
    print(f"[1/2] Exporting 30 candles for {SYMBOL}...")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, os.path.join(BOT_DIR, "export.py"), SYMBOL],
        capture_output=True,
        text=True,
        cwd=BOT_DIR,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    print(result.stdout.strip())
    if result.returncode != 0:
        print(f"ERROR: export.py failed:\n{result.stderr.strip()}")
        sys.exit(1)


def run_bots():
    print(f"\n[2/2] Running {len(BOTS)} indicator bots...\n")
    results = {}

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    for bot in BOTS:
        script = os.path.join(BOT_DIR, bot)
        result = subprocess.run(
            [sys.executable, script],
            capture_output=True,
            text=True,
            cwd=BOT_DIR,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        if result.returncode != 0:
            err = result.stderr.strip()
            print(f"  FAIL  {bot}: {err[:120]}")
            results[bot] = {"error": err}
            continue

        stdout = result.stdout.strip()
        json_start = stdout.rfind("{")
        json_end = stdout.rfind("}") + 1
        if json_start != -1 and json_end > json_start:
            try:
                data = json.loads(stdout[json_start:json_end])
                results[bot] = data
                pred = data.get("prediction", "?")
                conf = data.get("confidence", "?")
                print(f"  OK    {bot:25s} -> {pred:8s} ({conf})")
            except json.JSONDecodeError:
                results[bot] = {"error": "JSON parse failed", "raw": stdout[:200]}
                print(f"  FAIL  {bot}: JSON parse failed")
        else:
            results[bot] = {"error": "No JSON in output"}
            print(f"  FAIL  {bot}: no JSON output")

    return results


def main():
    print("=" * 60)
    print(f"  MT5 Ensemble Bot Runner - {SYMBOL}")
    print("=" * 60)

    run_export()
    results = run_bots()

    final = {
        "symbol": SYMBOL,
        "bot_count": len(BOTS),
        "results": results,
    }

    out_file = os.path.join(BOT_DIR, "ensemble_output.json")
    with open(out_file, "w") as f:
        json.dump(final, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"  Ensemble results saved to: {out_file}")
    print(f"{'=' * 60}")

    predictions = [r.get("prediction") for r in results.values() if "prediction" in r]
    bullish = predictions.count("bullish")
    bearish = predictions.count("bearish")
    neutral = predictions.count("neutral")

    print(f"\n  SUMMARY: {bullish} bullish | {bearish} bearish | {neutral} neutral")
    if bullish > bearish:
        print(f"  ENSEMBLE SIGNAL: BULLISH ({bullish}/{len(predictions)})")
    elif bearish > bullish:
        print(f"  ENSEMBLE SIGNAL: BEARISH ({bearish}/{len(predictions)})")
    else:
        print(f"  ENSEMBLE SIGNAL: NEUTRAL / MIXED")
    print()


if __name__ == "__main__":
    main()
