#!/usr/bin/env python3
"""
HTML Report Generator for Trading Bot Trades
Reads trades.json and exports a styled report (report.html) with statistics,
trade table, and profit curve chart.
"""

import json
import os
from datetime import datetime

# ================== CONFIG ==================
INPUT_JSON = "trades.json"
OUTPUT_HTML = "report.html"
CHART_JS_CDN = "https://cdn.jsdelivr.net/npm/chart.js"

# ============================================

def load_trades(file_path):
    """Load trades from JSON file."""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            if not isinstance(data, list):
                print("Warning: trades.json is not a list. Treating as empty.")
                return []
            return data
    except FileNotFoundError:
        print(f"File {file_path} not found. No trades to report.")
        return []
    except json.JSONDecodeError:
        print(f"Error decoding {file_path}. Empty or invalid JSON.")
        return []

def compute_stats(trades):
    """Compute summary statistics from trade list."""
    total_trades = len(trades)
    if total_trades == 0:
        return {
            "total": 0, "wins": 0, "losses": 0,
            "total_profit_pts": 0, "total_profit_currency": 0,
            "max_profit_pts": 0, "max_loss_pts": 0,
            "avg_profit_pts": 0, "avg_loss_pts": 0,
            "win_rate": 0,
            "cumulative_pts": []
        }

    profits_pts = []
    profits_cur = []
    winners_pts = []
    losers_pts = []

    for t in trades:
        # Try to get profit points (use 0 if missing)
        pts = t.get("profit_points")
        if pts is None:
            # Try to compute from close/open if point available, but we'll just skip
            pts = 0
        profits_pts.append(pts)
        cur = t.get("profit", 0)
        profits_cur.append(cur)

        if pts > 0:
            winners_pts.append(pts)
        elif pts < 0:
            losers_pts.append(pts)

    wins = len(winners_pts)
    losses = len(losers_pts)
    total_profit_pts = sum(profits_pts)
    total_profit_currency = sum(profits_cur)

    max_profit_pts = max(profits_pts) if profits_pts else 0
    max_loss_pts = min(profits_pts) if profits_pts else 0

    avg_profit_pts = sum(winners_pts) / wins if wins > 0 else 0
    avg_loss_pts = sum(losers_pts) / losses if losses > 0 else 0

    win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0

    # Cumulative sum for chart
    cumulative = []
    running = 0
    for p in profits_pts:
        running += p
        cumulative.append(round(running, 2))

    return {
        "total": total_trades,
        "wins": wins,
        "losses": losses,
        "total_profit_pts": total_profit_pts,
        "total_profit_currency": total_profit_currency,
        "max_profit_pts": max_profit_pts,
        "max_loss_pts": max_loss_pts,
        "avg_profit_pts": avg_profit_pts,
        "avg_loss_pts": avg_loss_pts,
        "win_rate": win_rate,
        "cumulative_pts": cumulative
    }

def format_datetime(dt_str):
    """Format ISO datetime to readable string."""
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return dt_str

def generate_html(trades, stats):
    """Generate complete HTML report."""
    total_trades = stats["total"]

    # Prepare table rows
    table_rows = ""
    for idx, t in enumerate(trades, 1):
        ticket = t.get("ticket", "N/A")
        symbol = t.get("symbol", "N/A")
        direction = t.get("direction", "N/A").upper()
        open_time = format_datetime(t.get("open_time", ""))
        close_time = format_datetime(t.get("close_time", ""))
        open_price = t.get("open_price", 0)
        close_price = t.get("close_price", 0)
        profit_pts = t.get("profit_points", 0)
        profit_cur = t.get("profit", 0)
        close_reason = t.get("close_reason", "Unknown")
        final_sl = t.get("final_sl_points", "N/A")

        # Row styling based on profit
        profit_class = "positive" if profit_pts > 0 else "negative" if profit_pts < 0 else "neutral"

        table_rows += f"""
        <tr>
            <td>{idx}</td>
            <td>{ticket}</td>
            <td>{symbol}</td>
            <td>{direction}</td>
            <td>{open_time}</td>
            <td>{close_time}</td>
            <td>{open_price:.2f}</td>
            <td>{close_price:.2f}</td>
            <td class="{profit_class}">{profit_pts:.1f}</td>
            <td class="{profit_class}">{profit_cur:.2f}</td>
            <td>{close_reason}</td>
            <td>{final_sl}</td>
        </tr>
        """

    # Prepare cumulative profit data for chart
    cumulative = stats["cumulative_pts"]
    chart_labels = [f"Trade {i+1}" for i in range(len(cumulative))]

    # Build HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trading Bot Execution Report</title>
    <script src="{CHART_JS_CDN}"></script>
    <style>
        * {{
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }}
        body {{
            background: #f5f7fa;
            margin: 20px;
            padding: 0;
            color: #1e293b;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 25px 30px;
            border-radius: 16px;
            box-shadow: 0 8px 20px rgba(0,0,0,0.05);
        }}
        h1 {{
            font-size: 2.2rem;
            font-weight: 600;
            margin-bottom: 0.2em;
            color: #0f172a;
        }}
        .subtitle {{
            color: #64748b;
            font-size: 0.95rem;
            margin-bottom: 2em;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 0.8em;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: #f8fafc;
            border-radius: 12px;
            padding: 14px 16px;
            border-left: 4px solid #3b82f6;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }}
        .stat-card .label {{
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #64748b;
            font-weight: 600;
        }}
        .stat-card .value {{
            font-size: 1.6rem;
            font-weight: 700;
            margin-top: 4px;
            line-height: 1.2;
        }}
        .stat-card .value.positive {{ color: #22c55e; }}
        .stat-card .value.negative {{ color: #ef4444; }}
        .stat-card .value.neutral {{ color: #f59e0b; }}
        .chart-container {{
            background: #fafcfd;
            border-radius: 12px;
            padding: 20px 15px 10px 15px;
            margin: 25px 0 30px 0;
            border: 1px solid #e9edf2;
        }}
        .chart-container h3 {{
            margin-top: 0;
            margin-bottom: 10px;
            font-weight: 500;
            color: #1e293b;
        }}
        .table-container {{
            overflow-x: auto;
            margin-top: 20px;
            border-radius: 12px;
            border: 1px solid #e9edf2;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
            min-width: 800px;
        }}
        thead {{
            background: #f1f5f9;
            border-bottom: 2px solid #d1d9e6;
        }}
        th {{
            padding: 12px 10px;
            text-align: left;
            font-weight: 600;
            color: #334155;
            white-space: nowrap;
        }}
        td {{
            padding: 10px 10px;
            border-bottom: 1px solid #e9edf2;
        }}
        tbody tr:nth-child(even) {{
            background-color: #fafbfc;
        }}
        tbody tr:hover {{
            background-color: #f0f4fe;
        }}
        .positive {{ color: #22c55e; font-weight: 600; }}
        .negative {{ color: #ef4444; font-weight: 600; }}
        .neutral {{ color: #f59e0b; }}
        .footer {{
            margin-top: 30px;
            font-size: 0.8rem;
            color: #94a3b8;
            text-align: right;
            border-top: 1px solid #e2e8f0;
            padding-top: 15px;
        }}
        @media (max-width: 600px) {{
            .container {{ padding: 15px; }}
            .stat-card .value {{ font-size: 1.2rem; }}
        }}
    </style>
</head>
<body>
<div class="container">
    <h1>📊 Trading Bot Execution Report</h1>
    <div class="subtitle">
        Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp; Total trades: {total_trades}
    </div>

    <!-- Summary Stats -->
    <div class="stats-grid">
        <div class="stat-card">
            <div class="label">Total Trades</div>
            <div class="value">{stats["total"]}</div>
        </div>
        <div class="stat-card">
            <div class="label">Wins / Losses</div>
            <div class="value">{stats["wins"]} / {stats["losses"]}</div>
        </div>
        <div class="stat-card">
            <div class="label">Win Rate</div>
            <div class="value">{stats["win_rate"]:.1f}%</div>
        </div>
        <div class="stat-card">
            <div class="label">Total Profit (pts)</div>
            <div class="value {'positive' if stats['total_profit_pts'] > 0 else 'negative' if stats['total_profit_pts'] < 0 else 'neutral'}">{stats["total_profit_pts"]:.1f}</div>
        </div>
        <div class="stat-card">
            <div class="label">Total Profit (currency)</div>
            <div class="value {'positive' if stats['total_profit_currency'] > 0 else 'negative' if stats['total_profit_currency'] < 0 else 'neutral'}">{stats["total_profit_currency"]:.2f}</div>
        </div>
        <div class="stat-card">
            <div class="label">Max Profit (pts)</div>
            <div class="value positive">{stats["max_profit_pts"]:.1f}</div>
        </div>
        <div class="stat-card">
            <div class="label">Max Loss (pts)</div>
            <div class="value negative">{stats["max_loss_pts"]:.1f}</div>
        </div>
        <div class="stat-card">
            <div class="label">Avg Win (pts)</div>
            <div class="value positive">{stats["avg_profit_pts"]:.1f}</div>
        </div>
        <div class="stat-card">
            <div class="label">Avg Loss (pts)</div>
            <div class="value negative">{stats["avg_loss_pts"]:.1f}</div>
        </div>
    </div>

    <!-- Profit Chart -->
    <div class="chart-container">
        <h3>📈 Cumulative Profit Over Trades</h3>
        <canvas id="profitChart" width="400" height="200"></canvas>
    </div>

    <!-- Trade Table -->
    <h3 style="margin-top: 25px; margin-bottom: 10px;">📋 Trade Details</h3>
    <div class="table-container">
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Ticket</th>
                    <th>Symbol</th>
                    <th>Direction</th>
                    <th>Open Time</th>
                    <th>Close Time</th>
                    <th>Open Price</th>
                    <th>Close Price</th>
                    <th>Profit (pts)</th>
                    <th>Profit (cur)</th>
                    <th>Close Reason</th>
                    <th>Final SL (pts)</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>
    </div>

    <div class="footer">
        Report generated automatically from trades.json • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </div>
</div>

<script>
    // === Chart.js cumulative profit chart ===
    (function() {{
        const ctx = document.getElementById('profitChart').getContext('2d');
        const labels = {json.dumps(chart_labels)};
        const dataPoints = {json.dumps(cumulative)};

        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [{{
                    label: 'Cumulative Profit (points)',
                    data: dataPoints,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 2,
                    tension: 0.1,
                    fill: true,
                    pointRadius: 2,
                    pointBackgroundColor: '#3b82f6'
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: true,
                plugins: {{
                    legend: {{
                        display: true,
                        position: 'top',
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        title: {{
                            display: true,
                            text: 'Profit (points)'
                        }}
                    }},
                    x: {{
                        title: {{
                            display: true,
                            text: 'Trade Sequence'
                        }}
                    }}
                }}
            }}
        }});
    }})();
</script>

</body>
</html>
"""

    return html

def main():
    trades = load_trades(INPUT_JSON)
    if not trades:
        print("No trades found. Generating empty report with zero stats.")
    stats = compute_stats(trades)
    html_content = generate_html(trades, stats)

    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"✅ Report generated: {OUTPUT_HTML}")
    print(f"   Total trades: {stats['total']}")
    print(f"   Win rate: {stats['win_rate']:.1f}%")
    print(f"   Total profit: {stats['total_profit_pts']:.1f} pts / {stats['total_profit_currency']:.2f} cur")

if __name__ == "__main__":
    main()