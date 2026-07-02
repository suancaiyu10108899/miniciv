# prototype/ai_dqn_trained.py — DQN with pretrained weights, compatible with eval.py
#
# Wraps DQNAgent with saved weights so it can be used in eval_matrix like any other AI.
# Usage: python -m prototype.eval_matrix --ais dqn_trained,greedy --games 200 --paired

import json, os
import random as _random
import numpy as np

from prototype.ai_dqn import DQNAgent, ai_decide as _dqn_decide, compute_features

_WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "..", "eval_paradigms", "dqn_best_weights.json")
_AGENT = None  # lazy init — loaded once per process


def _get_agent() -> DQNAgent:
    global _AGENT
    if _AGENT is None:
        weights_path = os.path.normpath(_WEIGHTS_PATH)
        if not os.path.exists(weights_path):
            raise FileNotFoundError(f"DQN weights not found: {weights_path}")
        _AGENT = DQNAgent(n_features=25, n_actions=6)
        _AGENT.load(weights_path)
        _AGENT.epsilon = 0.0  # pure exploitation in eval
    return _AGENT


def ai_decide(gs, pid: int, rng=None) -> list[dict]:
    """Eval-compatible decision function using trained DQN."""
    if rng is None:
        rng = _random.Random(gs.seed + gs.turn * 1000 + pid)
    return _dqn_decide(gs, pid, rng, dqn=_get_agent())
