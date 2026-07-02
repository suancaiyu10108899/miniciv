# prototype/run_all.py — Master runner for all agent experiments
"""Run all pending experiments that agents prepared but couldn't execute."""
import subprocess, sys, os, json, time
from datetime import datetime

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def run(cmd, timeout=600):
    log(f"RUN: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    if result.stdout:
        for line in result.stdout.split('\n')[-10:]:
            if line.strip(): print(f"  {line.strip()}")
    if result.returncode != 0:
        log(f"ERROR (code {result.returncode}): {result.stderr[-200:]}")
    return result.returncode == 0

def main():
    log("=== Master Experiment Runner ===")

    # 1. First validate everything loads
    log("Step 0: Validation")
    run("python -m pytest tests/ -q", 30)

    # 2. Run DQN training (Agent D)
    log("Step 1: DQN Training")
    run("python -m prototype.train_dqn", 600)

    # 3. Run self-play training (Agent D)
    log("Step 2: Self-Play Training")
    run("python -m prototype.train_selfplay", 600)

    # 4. Run hybrid AI training (Agent D)
    log("Step 3: Hybrid AI Training")
    run("python -m prototype.ai_hybrid", 300)

    # 5. Run cross-paradigm eval (Agent D)
    log("Step 4: Cross-Paradigm Eval")
    run("python -m prototype.eval_cross", 300)

    log("=== All experiments complete ===")

if __name__ == "__main__":
    main()
