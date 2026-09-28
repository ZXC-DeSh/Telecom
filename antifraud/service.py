import logging

from .features import extract_features
from .schemas import CallStart, NumberQuery

log = logging.getLogger(__name__)
EMERGENCY_CODES = frozenset({"101", "102", "103", "104", "112"})


class ScoringService:
    def __init__(self, store, model=None):
        self.store = store
        self.model = model

    @staticmethod
    def safe_result(reason, status="protected", protection=None):
        return {"status": status, "risk_score": None, "action": "allow",
                "auto_block": False, "reason": reason, "protection": protection, "factors": []}

    def score_call(self, call: CallStart):
        # Emergency protection has no dependency on model, CDR database or registry.
        if call.callee in EMERGENCY_CODES or call.destination_service == "emergency":
            result = self.safe_result("Экстренный вызов проходит без ожидания скоринга",
                                      protection={"kind": "emergency_destination"})
        else:
            try:
                protection = self.store.protection(call)
                if protection:
                    result = self.safe_result(protection["reason"], protection=protection)
                else:
                    features, n = extract_features(self.store.history(call.started_at), call)
                    if n < 5:
                        result = self.safe_result("Недостаточно истории для надёжной оценки", "insufficient_data")
                        result.update({"history_calls": n, "features": features})
                    elif self.model is None:
                        result = self.safe_result("Модель недоступна, вызов пропускается", "degraded")
                    else:
                        result = self.model.predict(features)
                        threshold = self.model.artifact["review_threshold"]
                        action = "review" if result["model_output"] >= threshold else "allow"
                        result.update({"status": "scored", "action": action, "auto_block": False,
                                       "protection": None, "features": features, "history_calls": n,
                                       "review_threshold": threshold,
                                       "reason": "Рекомендована проверка оператором" if action == "review" else "Порог проверки не достигнут"})
            except Exception:
                log.exception("Scoring failed; returning allow without a score")
                result = self.safe_result("Ошибка скоринга, вызов пропускается", "degraded")
        result["call_id"] = call.call_id
        # Emergency path must not wait for synchronous database I/O.
        if (result.get("protection") or {}).get("kind") == "emergency_destination":
            result["audit_status"] = "upstream_required"
            return result
        try:
            self.store.record_decision(call.call_id, result)
            result["audit_status"] = "recorded"
        except Exception:
            log.exception("Decision audit unavailable")
            result["audit_status"] = "unavailable"
        return result

    def score_number(self, query: NumberQuery):
        try:
            history = [h for h in self.store.history(query.at) if h.caller == query.number]
            if not history:
                return {"number": query.number, "at": query.at.isoformat(),
                        **self.safe_result("История номера отсутствует", "insufficient_data")}
            latest = max(history, key=lambda c: c.started_at)
            call = CallStart.model_validate({**latest.model_dump(include=set(CallStart.model_fields)),
                "call_id": "number-assessment", "started_at": query.at, "callee": "test:assessment",
                "destination_service": "ordinary"})
            features, n = extract_features(history=self.store.history(query.at), call=call)
            if n < 5 or self.model is None:
                result = self.safe_result("Недостаточно истории или модель недоступна", "insufficient_data" if n < 5 else "degraded")
            else:
                prediction = self.model.predict(features)
                result = {**prediction, "status": "scored", "auto_block": False,
                          "action": "review" if prediction["model_output"] >= self.model.artifact["review_threshold"] else "allow"}
            return {**result, "number": query.number, "at": query.at.isoformat(), "history_calls": n,
                    "context": "Метаданные последнего доступного вызова; это не пожизненный рейтинг владельца номера"}
        except Exception:
            log.exception("Number scoring failed")
            return {"number": query.number, **self.safe_result("Сервис временно недоступен", "degraded")}
