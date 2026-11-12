"""Train a small structural-feature overflow memory.

Input: 12 hand-written seeds and identifier/size mutations.
Model: standardized structural features + multinomial logistic regression.
Export: JSON coefficients, so the FastAPI runtime needs no numpy/sklearn.
This is an offline synthetic training run, not a general C/binary model.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.overflow_features import FEATURE_NAMES, vector  # noqa: E402
from generate_overflow_corpus import generate, load_seeds  # noqa: E402

KNOWLEDGE = ROOT / "knowledge"


def fit(x, y, seed):
    scaler = StandardScaler()
    matrix = scaler.fit_transform(np.asarray(x, dtype=float))
    model = LogisticRegression(max_iter=4000, class_weight="balanced", random_state=seed)
    model.fit(matrix, y)
    return scaler, model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20261112)
    args = parser.parse_args()
    rows = generate(args.count, args.seed)
    texts = [row["code"] for row in rows]
    labels = [row["cwe"] for row in rows]
    features = [vector(code) for code in texts]

    x_train, x_test, y_train, y_test = train_test_split(
        features, labels, test_size=0.2, random_state=args.seed, stratify=labels
    )
    x_seed, x_pool, y_seed, y_pool = train_test_split(
        x_train, y_train, test_size=0.8, random_state=args.seed, stratify=y_train
    )
    scaler, initial = fit(x_seed, y_seed, args.seed)
    pool_matrix = scaler.transform(np.asarray(x_pool, dtype=float))
    probs = initial.predict_proba(pool_matrix)
    pred = initial.predict(pool_matrix)
    keep = probs.max(axis=1) >= 0.70
    x_aug = x_seed + [row for row, take in zip(x_pool, keep) if take]
    y_aug = y_seed + [label for label, take in zip(pred, keep) if take]
    scaler, final = fit(x_aug, y_aug, args.seed)
    test_pred = final.predict(scaler.transform(np.asarray(x_test, dtype=float)))
    initial_pred = initial.predict(scaler.transform(np.asarray(x_test, dtype=float)))
    metrics = {
        "initial_accuracy": round(float(accuracy_score(y_test, initial_pred)), 4),
        "final_accuracy": round(float(accuracy_score(y_test, test_pred)), 4),
        "final_macro_f1": round(float(f1_score(y_test, test_pred, average="macro")), 4),
        "test_rows": len(y_test), "pseudo_labeled": int(keep.sum()),
        "seed_rows": len(x_seed), "classes": sorted(set(labels)),
        "classification_report": classification_report(y_test, test_pred, output_dict=True, zero_division=0),
    }

    # Harder check: hold out every variant of a whole seed.
    folds = []
    for held_seed in sorted({row["seed"] for row in rows}):
        train_rows = [row for row in rows if row["seed"] != held_seed]
        held_rows = [row for row in rows if row["seed"] == held_seed]
        fold_scaler, fold_model = fit([vector(row["code"]) for row in train_rows],
                                      [row["cwe"] for row in train_rows], args.seed)
        fold_pred = fold_model.predict(fold_scaler.transform(np.asarray([vector(row["code"]) for row in held_rows])))
        folds.append({"seed": held_seed, "rows": len(held_rows),
                      "accuracy": round(float(accuracy_score([row["cwe"] for row in held_rows], fold_pred)), 4)})
    metrics["leave_one_seed_out_accuracy"] = round(float(np.mean([x["accuracy"] for x in folds])), 4)
    metrics["leave_one_seed_out_folds"] = folds

    seed_labels, seed_codes = load_seeds()
    seed_matrix = scaler.transform(np.asarray([vector(seed_codes[item["id"]]) for item in seed_labels]))
    seed_probs = final.predict_proba(seed_matrix)
    seed_pred = final.predict(seed_matrix)
    seed_results = []
    for item, prediction, probabilities in zip(seed_labels, seed_pred, seed_probs):
        seed_results.append({
            "id": item["id"], "expected": item["cwe"], "predicted": str(prediction),
            "confidence": round(float(max(probabilities)), 4),
            "correct": str(prediction) == item["cwe"],
        })

    model_json = {
        "schema": 1,
        "family": "structural-features+logistic-regression",
        "features": FEATURE_NAMES,
        "classes": [str(c) for c in final.classes_],
        "mean": [float(x) for x in scaler.mean_],
        "scale": [float(x) for x in scaler.scale_],
        "coef": [[float(x) for x in row] for row in final.coef_],
        "intercept": [float(x) for x in final.intercept_],
        "abstract_identifiers": True,
    }
    KNOWLEDGE.mkdir(parents=True, exist_ok=True)
    (KNOWLEDGE / "overflow_model.json").write_text(json.dumps(model_json, ensure_ascii=False) + "\n", encoding="utf-8")
    kb = {
        "schema": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
        "name": "overflow-candidate-memory",
        "corpus": {"seeds": len(seed_labels), "variants": len(rows), "count_per_seed": args.count},
        "model": {"family": "structural-features+logistic-regression", "version": 1, "file": "overflow_model.json"},
        "feature_count": len(FEATURE_NAMES), "metrics": metrics,
        "seed_results": seed_results, "classes": sorted(set(labels)),
        "patterns": [{"cwe": i["cwe"], "group": i["group"], "rule": i["expected_rule"],
                      "root_cause": i["root_cause"], "fix": i["fix"]} for i in seed_labels],
        "limits": [
            "Synthetic mutations of 12 seeds; not representative of all C, binaries or real-world projects.",
            "Rules remain authoritative; this memory is a candidate/ranking aid and cannot verify a patch.",
            "No runtime weight updates; retraining is an explicit offline script.",
        ],
    }
    (KNOWLEDGE / "overflow_kb.json").write_text(json.dumps(kb, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"metrics": metrics, "seeds": seed_results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
