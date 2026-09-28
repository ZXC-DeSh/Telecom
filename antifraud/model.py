import json
import math
from pathlib import Path

from .features import FEATURE_NAMES, FEATURE_LABELS


class RiskModel:
    """Расчёт по параметрам модели из JSON без загрузки исполняемых объектов pickle."""
    def __init__(self, artifact: dict):
        if artifact["feature_names"] != FEATURE_NAMES:
            raise ValueError("Набор признаков модели не совпадает с набором приложения")
        for key in ("mean", "scale", "coef"):
            if len(artifact[key]) != len(FEATURE_NAMES) or not all(math.isfinite(v) for v in artifact[key]):
                raise ValueError("Некорректные параметры модели")
        if any(v <= 0 for v in artifact["scale"]) or not math.isfinite(artifact["intercept"]):
            raise ValueError("Некорректные параметры нормализации модели")
        self.artifact = artifact

    @classmethod
    def load(cls, path):
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def predict(self, features: dict) -> dict:
        a = self.artifact
        contributions = []
        z = float(a["intercept"])
        for i, name in enumerate(FEATURE_NAMES):
            term = (features[name] - a["mean"][i]) / a["scale"][i] * a["coef"][i]
            z += term
            contributions.append({"feature": name, "description": FEATURE_LABELS[name],
                                  "value": features[name], "log_odds_contribution": term})
        probability = 1 / (1 + math.exp(-max(-700, min(700, z))))
        return {"risk_score": round(probability * 100, 2),
                "model_output": probability,
                "score_meaning": "Индекс риска 0–100, не подтверждённая вероятность мошенничества",
                "model_version": a["version"], "baseline_log_odds": a["intercept"],
                "total_log_odds": z,
                "contribution_unit": "log_odds; вклады не являются процентными пунктами",
                "factors": sorted(contributions, key=lambda x: abs(x["log_odds_contribution"]), reverse=True)}
