# prototype/train_bc.py — Behavior Cloning Training Script
# Trains a 2-layer NN to clone Greedy AI behavior

import json, os, sys, math, random
import numpy as np

# Ensure we can import prototype modules
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from prototype.game import init_game, step_game
from prototype.eval import load_ai
from prototype.ai_bc import (
    _extract_features, _action_to_index, N_FEATURES, N_ACTIONS,
    _index_to_action,
)


def generate_training_data(n_games=2000, size=15, seed=42,
                           ai0_name="greedy", ai1_name="greedy_v2",
                           max_turns=100) -> list:
    """Generate training data: for each turn, record features -> Greedy's chosen action."""
    ai0 = load_ai(ai0_name)
    ai1 = load_ai(ai1_name)

    data = []  # list of (features, action_idx) tuples
    skipped = {"no_actions": 0, "no_unit_actions": 0}

    for g in range(n_games):
        game_seed = seed + g * 1000
        gs = init_game(seed=game_seed, size=size, generator_id="balanced")
        rng0 = random.Random(game_seed)
        rng1 = random.Random(game_seed + 1)

        while gs.winner is None and gs.turn < max_turns:
            p0_actions = ai0(gs, 0, rng0)
            p1_actions = ai1(gs, 1, rng1)

            # Record P0 (greedy) actions for BC training
            units_p0 = [u for u in gs.units if u.player_id == 0 and u.alive]
            done_p0 = set()

            for act in p0_actions:
                ui = act.get("unit_idx", -1)
                if ui >= 0 and ui < len(units_p0):
                    if ui in done_p0:
                        continue
                    # Unit action
                    features = _extract_features(gs, 0, ui)
                    action_idx = _action_to_index(act, ui, gs, 0)
                    data.append((features.tolist(), action_idx))
                    done_p0.add(ui)
                elif ui == -1:
                    # City-level action (production/research/non-unit)
                    features = _extract_features(gs, 0, None)
                    action_idx = _action_to_index(act, -1, gs, 0)
                    data.append((features.tolist(), action_idx))

            step_game(gs, p0_actions, p1_actions)

        if (g + 1) % 200 == 0:
            print(f"  Generated {g+1}/{n_games} games, {len(data)} samples")

    print(f"\nTotal: {len(data)} training samples from {n_games} games")
    return data


def initialize_weights():
    """Initialize 3-layer NN weights with Xavier init."""
    np.random.seed(42)
    weights = {
        "W1": np.random.randn(N_FEATURES, 64).astype(np.float32) * np.sqrt(2.0 / N_FEATURES),
        "b1": np.zeros(64, dtype=np.float32),
        "W2": np.random.randn(64, 32).astype(np.float32) * np.sqrt(2.0 / 64),
        "b2": np.zeros(32, dtype=np.float32),
        "W3": np.random.randn(32, N_ACTIONS).astype(np.float32) * np.sqrt(2.0 / 32),
        "b3": np.zeros(N_ACTIONS, dtype=np.float32),
    }
    return weights


def forward(features, weights):
    """Forward pass: N_FEATURES -> 64 -> 32 -> N_ACTIONS"""
    h1 = np.dot(features, weights["W1"]) + weights["b1"]
    h1 = np.maximum(0, h1)  # ReLU

    h2 = np.dot(h1, weights["W2"]) + weights["b2"]
    h2 = np.maximum(0, h2)  # ReLU

    output = np.dot(h2, weights["W3"]) + weights["b3"]
    return output, h1, h2


def softmax(x):
    """Stable softmax."""
    x = x - np.max(x, axis=-1, keepdims=True)
    exp_x = np.exp(x)
    return exp_x / np.sum(exp_x, axis=-1, keepdims=True)


def cross_entropy_loss(scores, targets):
    """Cross-entropy loss with softmax."""
    probs = softmax(scores)
    n = len(targets)
    log_probs = -np.log(probs[np.arange(n), targets] + 1e-10)
    return np.mean(log_probs)


def accuracy(scores, targets):
    """Compute accuracy."""
    preds = np.argmax(scores, axis=1)
    return np.mean(preds == targets)


def train(data, weights, epochs=50, batch_size=32, lr=0.01):
    """Train the NN using SGD with mini-batches."""
    n = len(data)
    features = np.array([d[0] for d in data], dtype=np.float32)
    targets = np.array([d[1] for d in data], dtype=np.int64)

    # Shuffle
    indices = np.arange(n)

    best_loss = float("inf")
    best_weights = None
    history = {"loss": [], "accuracy": []}

    for epoch in range(epochs):
        np.random.shuffle(indices)
        epoch_loss = 0.0
        epoch_acc = 0.0
        n_batches = 0

        for start in range(0, n, batch_size):
            end = min(start + batch_size, n)
            batch_idx = indices[start:end]
            batch_feat = features[batch_idx]
            batch_targ = targets[batch_idx]

            # Forward
            scores, h1, h2 = forward(batch_feat, weights)
            probs = softmax(scores)

            # Loss
            batch_loss = cross_entropy_loss(scores, batch_targ)

            # Backward (manual gradients)
            batch_size_actual = len(batch_feat)

            # dL/dscores = probs - one_hot(target)
            dscores = probs.copy()
            dscores[np.arange(batch_size_actual), batch_targ] -= 1
            dscores /= batch_size_actual

            # Gradient for W3, b3
            dW3 = np.dot(h2.T, dscores)
            db3 = np.sum(dscores, axis=0)

            # Backprop to h2
            dh2 = np.dot(dscores, weights["W3"].T)
            dh2[h2 <= 0] = 0  # ReLU backward

            # Gradient for W2, b2
            dW2 = np.dot(h1.T, dh2)
            db2 = np.sum(dh2, axis=0)

            # Backprop to h1
            dh1 = np.dot(dh2, weights["W2"].T)
            dh1[h1 <= 0] = 0  # ReLU backward

            # Gradient for W1, b1
            dW1 = np.dot(batch_feat.T, dh1)
            db1 = np.sum(dh1, axis=0)

            # SGD update
            weights["W3"] -= lr * dW3
            weights["b3"] -= lr * db3
            weights["W2"] -= lr * dW2
            weights["b2"] -= lr * db2
            weights["W1"] -= lr * dW1
            weights["b1"] -= lr * db1

            epoch_loss += batch_loss
            epoch_acc += accuracy(scores, batch_targ)
            n_batches += 1

        avg_loss = epoch_loss / n_batches
        avg_acc = epoch_acc / n_batches
        history["loss"].append(avg_loss)
        history["accuracy"].append(avg_acc)

        if avg_loss < best_loss:
            best_loss = avg_loss
            best_weights = {k: v.copy() for k, v in weights.items()}

        if (epoch + 1) % 5 == 0:
            print(f"  Epoch {epoch+1}/{epochs}: loss={avg_loss:.4f}, acc={avg_acc:.4f}")

    print(f"\nBest loss: {best_loss:.4f}")
    return best_weights, history


def save_weights(weights, path):
    """Save weights as JSON."""
    data = {k: v.tolist() for k, v in weights.items()}
    with open(path, "w") as f:
        json.dump(data, f)
    print(f"Saved weights to {path}")


def main():
    print("=" * 60)
    print("Behavior Cloning Training")
    print("=" * 60)

    # Step 1: Generate training data
    print("\n[Step 1] Generating training data...")
    n_games = 1000  # Reduced from 2000 for speed since we have limited compute
    data = generate_training_data(n_games=n_games, size=15,
                                  ai0_name="greedy_v2", ai1_name="aggressive")

    if len(data) == 0:
        print("ERROR: No training data generated!")
        return

    # Step 2: Initialize network
    print("\n[Step 2] Initializing neural network...")
    weights = initialize_weights()
    print(f"  Architecture: {N_FEATURES} -> 64 -> 32 -> {N_ACTIONS}")
    print(f"  Parameters: {sum(v.size for v in weights.values())}")

    # Step 3: Split into train/val
    np.random.seed(123)
    indices = np.arange(len(data))
    np.random.shuffle(indices)
    split = int(len(data) * 0.8)
    train_data = [data[i] for i in indices[:split]]
    val_data = [data[i] for i in indices[split:]]
    print(f"\n[Step 3] Split: {len(train_data)} train, {len(val_data)} val")

    # Step 4: Train
    print("\n[Step 4] Training...")
    lr = 0.01
    best_weights, history = train(train_data, weights, epochs=50,
                                  batch_size=64, lr=lr)

    # Step 5: Validate
    print("\n[Step 5] Validation...")
    val_features = np.array([d[0] for d in val_data], dtype=np.float32)
    val_targets = np.array([d[1] for d in val_data], dtype=np.int64)
    val_scores, _, _ = forward(val_features, best_weights)
    val_loss = cross_entropy_loss(val_scores, val_targets)
    val_acc = accuracy(val_scores, val_targets)
    print(f"  Validation loss: {val_loss:.4f}")
    print(f"  Validation accuracy: {val_acc:.4f}")

    # Step 6: Save weights
    weights_path = os.path.join(os.path.dirname(__file__), "bc_weights.json")
    save_weights(best_weights, weights_path)

    # Step 7: Save training history
    history_path = os.path.join(os.path.dirname(__file__), "bc_history.json")
    with open(history_path, "w") as f:
        json.dump(history, f)
    print(f"Saved training history to {history_path}")

    print("\n" + "=" * 60)
    print("Training complete!")
    print(f"  Samples: {len(data)}")
    print(f"  Val loss: {val_loss:.4f}")
    print(f"  Val accuracy: {val_acc:.4f}")
    print(f"  Weights: {weights_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
