import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, confusion_matrix, roc_auc_score
from sklearn.preprocessing import StandardScaler

from .features import FEATURE_NAMES
from .model import RiskModel


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def select_threshold(y, scores, max_fpr=.01):
    """Maximize validation recall under the empirical FPR budget; ties prefer higher threshold."""
    candidates = [float(s) for s in np.unique(scores)] + [1.000000001]
    feasible = []
    for threshold in candidates:
        pred = scores >= threshold
        fpr = float(np.mean(pred[y == 0]))
        recall = float(np.mean(pred[y == 1]))
        if fpr <= max_fpr:
            feasible.append((recall, -fpr, threshold))
    return max(feasible)[2]


def wilson_upper(k, n, z=1.96):
    if not n:
        return None
    p = k / n
    return (p + z*z/(2*n) + z*np.sqrt(p*(1-p)/n + z*z/(4*n*n))) / (1 + z*z/n)


def metrics(y, scores, threshold):
    tn, fp, fn, tp = confusion_matrix(y, scores >= threshold, labels=[0, 1]).ravel()
    return {"n": len(y), "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
            "fpr": float(fp / max(fp + tn, 1)), "fpr_wilson_95_upper": float(wilson_upper(fp, fp + tn)),
            "recall": float(tp / max(tp + fn, 1)), "precision": float(tp / max(tp + fp, 1)),
            "pr_auc": float(average_precision_score(y, scores)),
            "roc_auc": float(roc_auc_score(y, scores)), "brier": float(brier_score_loss(y, scores))}


def train(data=Path("data"), output=Path("artifacts")):
    data, output = Path(data), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    labels = {r["group_id"]: r for r in read_jsonl(data / "labels.jsonl")}
    rows = read_jsonl(data / "features.jsonl")
    splits = {}
    for split in ("train", "validation", "test"):
        chosen = [r for r in rows if r["split"] == split]
        splits[split] = (np.array([[r["features"][f] for f in FEATURE_NAMES] for r in chosen]),
                         np.array([labels[r["group_id"]]["label"] for r in chosen]), chosen)
    x, y, _ = splits["train"]
    scaler = StandardScaler().fit(x)
    classifier = LogisticRegression(C=.35, class_weight="balanced", max_iter=2000, random_state=42)
    classifier.fit(scaler.transform(x), y)
    xv, yv, _ = splits["validation"]
    pv = classifier.predict_proba(scaler.transform(xv))[:, 1]
    threshold = select_threshold(yv, pv)
    version_hash = hashlib.sha256((data / "features.jsonl").read_bytes() + (data / "labels.jsonl").read_bytes()).hexdigest()[:12]
    artifact = {"version": f"synthetic-logistic-{version_hash}", "feature_names": FEATURE_NAMES,
                "mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist(),
                "coef": classifier.coef_[0].tolist(), "intercept": float(classifier.intercept_[0]),
                "review_threshold": threshold, "synthetic_only": True, "sklearn_version": sklearn.__version__}
    portable = RiskModel(artifact)
    for row, expected in zip(xv, pv):
        actual = portable.predict(dict(zip(FEATURE_NAMES, row)))["model_output"]
        if abs(actual - expected) > 1e-10:
            raise AssertionError("Exported model does not match sklearn inference")
    report = {"synthetic_only": True, "warning": "Метрики только на синтетике; качество на закрытых данных не измерено.",
              "model_version": artifact["version"], "validation_fpr_budget": .01,
              "review_threshold": threshold, "explanation_export_max_error": 1e-10,
              "splits": {}, "test_by_scenario": {}}
    predictions = []
    for split, (xs, ys, selected) in splits.items():
        scores = classifier.predict_proba(scaler.transform(xs))[:, 1]
        report["splits"][split] = metrics(ys, scores, threshold)
        for row, truth, score in zip(selected, ys, scores):
            predictions.append({"group_id": row["group_id"], "split": split, "label": int(truth),
                                "risk_score": round(float(score) * 100, 2), "review": bool(score >= threshold)})
        if split == "test":
            for scenario in sorted({labels[r["group_id"]]["scenario"] for r in selected}):
                indices = [i for i, r in enumerate(selected) if labels[r["group_id"]]["scenario"] == scenario]
                report["test_by_scenario"][scenario] = {"n": len(indices),
                    "review_count": int(sum(scores[i] >= threshold for i in indices)),
                    "fraud": int(ys[indices[0]])}
    (output / "model.json").write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output / "predictions.jsonl").open("w", encoding="utf-8") as f:
        for prediction in predictions:
            f.write(json.dumps(prediction) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    train(args.data, args.output)
