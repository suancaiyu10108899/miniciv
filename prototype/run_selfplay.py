# prototype/run_selfplay.py — Run self-play training standalone
import subprocess, sys, time

def run(cmd, timeout=900):
    print(f"[{time.strftime('%H:%M:%S')}] RUN: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        for line in result.stdout.split('\n')[-20:]:
            if line.strip(): print(f"  {line.strip()}")
        if result.returncode != 0:
            print(f"  STDERR: {result.stderr[-300:]}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT after {timeout}s — partial results may be saved")
        return False

print("=== Self-Play Training ===")
run("python -m prototype.train_selfplay", 900)

print("\n=== Hybrid AI Training ===")
run("python -m prototype.ai_hybrid", 300)

print("\n=== Cross-Paradigm Eval ===")
run("python -m prototype.eval_cross", 300)

print("\nDone!")
