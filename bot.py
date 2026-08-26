#!/usr/bin/env python3
"""
bot.py - Read ensemble_output.json from json/ folder and conclude overall market sentiment.
The script aggregates predictions from multiple bots, optionally weighting by confidence,
and prints the conclusion (bullish/bearish) along with metadata.
"""

import json
import os
from datetime import datetime

# Path to the JSON file
JSON_FOLDER = "json"
JSON_FILE = "ensemble_output.json"
JSON_PATH = os.path.join(JSON_FOLDER, JSON_FILE)

# Confidence weights for aggregation
CONFIDENCE_WEIGHTS = {
    "low": 1,
    "moderate": 2,
    "high": 3
}

def load_ensemble_data(path):
    """Load and parse the ensemble JSON file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"JSON file not found: {path}")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def aggregate_predictions(results):
    """
    Aggregate predictions from all bots.
    Returns a dict with counts, weighted scores, and per-bot details.
    """
    bullish_count = 0
    bearish_count = 0
    neutral_count = 0
    weighted_bullish = 0
    weighted_bearish = 0
    per_bot = []

    for bot_name, bot_data in results.items():
        prediction = bot_data.get("prediction", "").lower()
        confidence = bot_data.get("confidence", "low").lower()
        weight = CONFIDENCE_WEIGHTS.get(confidence, 1)

        if prediction == "bullish":
            bullish_count += 1
            weighted_bullish += weight
        elif prediction == "bearish":
            bearish_count += 1
            weighted_bearish += weight
        else:
            neutral_count += 1  # if prediction is neutral/unknown

        per_bot.append({
            "bot": bot_name,
            "prediction": prediction,
            "confidence": confidence,
            "weight": weight
        })

    return {
        "bullish_count": bullish_count,
        "bearish_count": bearish_count,
        "neutral_count": neutral_count,
        "weighted_bullish": weighted_bullish,
        "weighted_bearish": weighted_bearish,
        "per_bot": per_bot
    }

def decide_conclusion(agg):
    """Decide final conclusion based on weighted scores, fallback to majority."""
    if agg["weighted_bullish"] > agg["weighted_bearish"]:
        return "BULLISH"
    elif agg["weighted_bearish"] > agg["weighted_bullish"]:
        return "BEARISH"
    else:
        # Tie in weighted scores -> use unweighted majority
        if agg["bullish_count"] > agg["bearish_count"]:
            return "BULLISH"
        elif agg["bearish_count"] > agg["bullish_count"]:
            return "BEARISH"
        else:
            return "NEUTRAL"

def print_summary(data, agg, conclusion, metadata):
    """Print a formatted summary of the ensemble conclusion."""
    symbol = data.get("symbol", "UNKNOWN")
    bot_count = data.get("bot_count", len(data.get("results", {})))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("=" * 60)
    print(f"ENSEMBLE ANALYSIS REPORT - {now}")
    print("=" * 60)
    print(f"Symbol: {symbol}")
    print(f"Total Bots: {bot_count}")
    print(f"Processed Bots: {len(agg['per_bot'])}")
    print("-" * 60)
    print(f"Bullish predictions (count): {agg['bullish_count']}")
    print(f"Bearish predictions (count): {agg['bearish_count']}")
    print(f"Neutral/Unknown predictions: {agg['neutral_count']}")
    print(f"Weighted Bullish Score: {agg['weighted_bullish']}")
    print(f"Weighted Bearish Score: {agg['weighted_bearish']}")
    print("-" * 60)
    print(f"*** OVERALL CONCLUSION: {conclusion} ***")
    print("=" * 60)

    # Print per-bot details
    print("\nPer-Bot Predictions:")
    print(f"{'Bot Name':<25} {'Prediction':<12} {'Confidence':<10} {'Weight':<6}")
    print("-" * 60)
    for bot in agg["per_bot"]:
        print(f"{bot['bot']:<25} {bot['prediction']:<12} {bot['confidence']:<10} {bot['weight']:<6}")

    # Print additional metadata if present
    if metadata:
        print("\nAdditional Metadata:")
        for key, value in metadata.items():
            print(f"  {key}: {value}")

def main():
    try:
        data = load_ensemble_data(JSON_PATH)
    except Exception as e:
        print(f"Error loading ensemble data: {e}")
        return

    results = data.get("results", {})
    if not results:
        print("No bot results found in JSON.")
        return

    # Aggregate predictions
    agg = aggregate_predictions(results)

    # Decide final conclusion
    conclusion = decide_conclusion(agg)

    # Gather metadata from top-level (excluding results for brevity)
    metadata = {k: v for k, v in data.items() if k != "results"}

    # Print summary
    print_summary(data, agg, conclusion, metadata)

if __name__ == "__main__":
    main()