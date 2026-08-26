import subprocess
import sys
import json
import os
import glob
import shutil

SYMBOL = "XAUUSD"
BOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot")
JSON_DIR = os.path.join("json")
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
    print(f"\n[2/2] Running {len(BOTS)-1} indicator bots...\n")
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
        json_start = stdout.find("{")
        if json_start != -1:
            try:
                data = json.loads(stdout[json_start:])
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


def move_json_to_folder():
    """Move generated JSON files (except candles.json) to the json/ directory."""
    os.makedirs(JSON_DIR, exist_ok=True)
    moved = 0
    for json_file in glob.glob(os.path.join(BOT_DIR, "*.json")):
        if os.path.basename(json_file) == "candles.json":
            continue
        dest = os.path.join(JSON_DIR, os.path.basename(json_file))
        shutil.move(json_file, dest)
        moved += 1
    print(f"  Moved {moved} JSON files to: {JSON_DIR}")


def run_conclusion():
    """
    Execute bot.py to read ensemble_output.json and print the final
    bullish/bearish conclusion along with metadata.
    """
    print("\n" + "=" * 60)
    print("  Running ensemble conclusion (bot.py)...")
    print("=" * 60)

    bot_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.py")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    result = subprocess.run(
        [sys.executable, bot_script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)


def main():
    print("=" * 60)
    print(f"  MT5 Ensemble Bot Runner - {SYMBOL}")
    print("=" * 60)

    # Step 1: export candles
    run_export()

    # Step 2: run all indicator bots
    results = run_bots()

    # Build ensemble_output.json
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

    # Quick summary from predictions (optional)
    predictions = [r.get("prediction") for r in results.values() if "prediction" in r]
    bullish = predictions.count("bullish")
    bearish = predictions.count("bearish")
    neutral = predictions.count("neutral")

    print(f"\n  QUICK SUMMARY: {bullish} bullish | {bearish} bearish | {neutral} neutral")
    if bullish > bearish:
        print(f"  QUICK SIGNAL: BULLISH ({bullish}/{len(predictions)})")
    elif bearish > bullish:
        print(f"  QUICK SIGNAL: BEARISH ({bearish}/{len(predictions)})")
    else:
        print(f"  QUICK SIGNAL: NEUTRAL / MIXED")
    print()

    # Move JSON files to json/ directory
    move_json_to_folder()

    # Run conclusion script (bot.py)
    run_conclusion()


if __name__ == "__main__":
    main()