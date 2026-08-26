import subprocess
import sys
import os
import shutil
from datetime import datetime

def run_script(name):
    print(f"\n{'='*60}")
    print(f"  Running {name}...")
    print(f"{'='*60}\n")
    result = subprocess.run([sys.executable, name])
    return result

def archive_report():
    report_file = "report.html"
    if not os.path.exists(report_file):
        print("No report.html found to archive.")
        return

    folder = "html-report"
    os.makedirs(folder, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_name = f"{timestamp}.report.html"
    dest = os.path.join(folder, new_name)

    shutil.move(report_file, dest)
    print(f"✅ Archived report to {dest}")

def main():
    while True:
        run_script("ai.py")
        run_script("trader.py")
        archive_report()

if __name__ == "__main__":
    main()