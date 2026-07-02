# prototype/train_bc.py — Behavior Cloning Training Script
# Trains a 2-layer NN (30->64->32->21) to clone Greedy AI behavior
import json, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from prototype.ai_bc import N_FEATURES, N_ACTIONS


def load_data(path="prototype/bc_training_data.json"):
    print("Loading data...", flush=True)
    data = json.load(open(path))
    print(f"Loaded {len(data)} samples", flush=True)
    features = np.array([d[0] for d in data], dtype=np.float32)
    targets = np.array([d[1] for d in data], dtype=np.int64)
    return features, targets


def init_weights():
    np.random.seed(42)
    return {
        "W1": np.random.randn(N_FEATURES, 64).astype(np.float32) * np.sqrt(2.0 / N_FEATURES),
        "b1": np.zeros(64, dtype=np.float32),
        "W2": np.random.randn(64, 32).astype(np.float32) * np.sqrt(2.0 / 64),
        "b2": np.zeros(32, dtype=np.float32),
        "W3": np.random.randn(32, N_ACTIONS).astype(np.float32) * np.sqrt(2.0 / 32),
        "b3": np.zeros(N_ACTIONS, dtype=np.float32),
    }


def forward(x, w):
    h1 = np.maximum(0, np.dot(x, w["W1"]) + w["b1"])
    h2 = np.maximum(0, np.dot(h1, w["W2"]) + w["b2"])
    out = np.dot(h2, w["W3"]) + w["b3"]
    return out, h1, h2


def softmax(x):
    x = x - np.max(x, axis=-1, keepdims=True)
    e = np.exp(x)
    return e / np.sum(e, axis=-1, keepdims=True)


def train(features, targets, epochs=50, batch_size=256, lr=0.01):
    n = len(features)
    np.random.seed(123)
    indices = np.arange(n)
    np.random.shuffle(indices)
    split = int(n * 0.8)
    train_idx, val_idx = indices[:split], indices[split:]
    train_feat, train_targ = features[train_idx], targets[train_idx]
    val_feat, val_targ = features[val_idx], targets[val_idx]
    print(f"Train: {len(train_feat)}, Val: {len(val_feat)}", flush=True)

    weights = init_weights()
    best_loss = float("inf")
    best_weights = None
    history = {"loss": [], "val_loss": [], "val_accuracy": []}
    t0 = time.time()

    for epoch in range(epochs):
        perm = np.random.permutation(len(train_feat))
        epoch_loss = 0.0
        n_batches = 0
        for start in range(0, len(train_feat), batch_size):
            end = min(start + batch_size, len(train_feat))
            idx = perm[start:end]
            bx, bt = train_feat[idx], train_targ[idx]
            scores, h1, h2 = forward(bx, weights)
            probs = softmax(scores)
            log_probs = -np.log(probs[np.arange(len(bt)), bt] + 1e-10)
            loss = np.mean(log_probs)
            dscores = probs.copy()
            dscores[np.arange(len(bt)), bt] -= 1
            dscores /= len(bt)
            dW3 = np.dot(h2.T, dscores)
            db3 = np.sum(dscores, axis=0)
            dh2 = np.dot(dscores, weights["W3"].T)
            dh2[h2 <= 0] = 0
            dW2 = np.dot(h1.T, dh2)
            db2 = np.sum(dh2, axis=0)
            dh1 = np.dot(dh2, weights["W2"].T)
            dh1[h1 <= 0] = 0
            dW1 = np.dot(bx.T, dh1)
            db1 = np.sum(dh1, axis=0)
            weights["W3"] -= lr * dW3
            weights["b3"] -= lr * db3
            weights["W2"] -= lr * dW2
            weights["b2"] -= lr * db2
            weights["W1"] -= lr * dW1
            weights["b1"] -= lr * db1
            epoch_loss += loss
            n_batches += 1
        avg_loss = epoch_loss / n_batches
        val_scores, _, _ = forward(val_feat, weights)
        val_probs = softmax(val_scores)
        val_log = -np.log(val_probs[np.arange(len(val_targ)), val_targ] + 1e-10)
        val_loss = float(np.mean(val_log))
        val_acc = float(np.mean(np.argmax(val_scores, axis=1) == val_targ))
        history["loss"].append(float(avg_loss))
        history["val_loss"].append(val_loss)
        history["val_accuracy"].append(val_acc)
        if avg_loss < best_loss:
            best_loss = avg_loss
            best_weights = {k: v.copy() for k, v in weights.items()}
        if (epoch + 1) % 5 == 0:
            elapsed = time.time() - t0
            print(f"Epoch {epoch+1}/{epochs}: loss={avg_loss:.4f} val_loss={val_loss:.4f} val_acc={val_acc:.4f} {elapsed:.0f}s", flush=True)

    print(f"Best loss: {best_loss:.4f}", flush=True)
    return best_weights, history


def main():
    features, targets = load_data()
    weights, history = train(features, targets)
    wdata = {k: v.tolist() for k, v in weights.items()}
    json.dump(wdata, open("prototype/bc_weights.json", "w"))
    json.dump(history, open("prototype/bc_history.json", "w"))
    print("Saved weights and history", flush=True)


if __name__ == "__main__":
    main()
