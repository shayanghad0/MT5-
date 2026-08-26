import subprocess
import sys

def run_script(name):
    print(f"\n{'='*60}")
    print(f"  Running {name}...")
    print(f"{'='*60}\n")
    subprocess.run([sys.executable, name])

def main():
    while True:
        run_script("ai.py")
        run_script("trader.py")

if __name__ == "__main__":
    main()
