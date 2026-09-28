"""Подготовленные звонки для визуальной демонстрации и простой реестр организаций."""
from datetime import timedelta
import random
from threading import Lock
from uuid import uuid4

from .generate import scenario
from .schemas import Approval, PrivilegeRequest
from .storage import utcnow


def add_demo_privilege(store, number, organization):
    """В демо проверку организации заменяет выбор известного подтверждённого источника."""
    now = utcnow()
    history = [h for h in store.history(now) if h.caller == number]
    if not history:
        raise ValueError("В истории нет этого номера. Сначала выберите пример или загрузите вызовы.")
    source = max(history, key=lambda h: h.started_at)
    if not source.caller_identity_verified:
        raise ValueError("Источник последнего вызова не подтверждён. Совпадения номера недостаточно для привилегии.")
    active = [r for r in store.list_requests() if r["number"] == number
              and r["status"] == "approved" and r["expires"] > now.timestamp()]
    if active:
        return active[0]
    request = store.request(organization, PrivilegeRequest(number=number, justification="Добавлено в локальном демонстрационном интерфейсе"))
    store.approve(request["id"], Approval(
        verified_subscriber_id=source.subscriber_id, verified_operator=source.source_operator,
        verified_trunk=source.ingress_trunk, evidence_reference="Локальная демонстрация",
        expires_at=now + timedelta(days=30)))
    return next(r for r in store.list_requests() if r["id"] == request["id"])


class DemoCatalog:
    def __init__(self, store):
        self.store = store
        self.items = None
        self.lock = Lock()

    def load(self):
        with self.lock:
            if self.items is not None:
                return self.items
            self.items = self._generate()
            return self.items

    def _generate(self):
        batch = uuid4().hex[:10]
        at = utcnow()
        presets = [
            ("mass", "fraud_mass_dial", "Массовый обзвон", "Много адресатов, короткие звонки", "+7 495 ***-**-12", "risk"),
            ("fanout", "fraud_fanout", "Согласованный веер", "Несколько номеров с общим шаблоном", "+7 499 ***-**-46", "risk"),
            ("personal", "personal", "Обычный абонент", "Небольшой круг постоянных контактов", "+7 916 ***-**-83", "normal"),
            ("hospital", "hospital", "Обратный звонок больницы", "Номер в реестре важных организаций", "+7 495 ***-**-03", "protected"),
            ("international", "international_family", "Звонок из-за рубежа", "Международные семейные контакты", "+49 30 ***-**-21", "normal"),
            ("quiet", "fraud_low_volume", "Малозаметный обзвон", "Редкие звонки со смешанными сигналами", "+7 921 ***-**-58", "mixed"),
        ]
        items = []
        for index, (key, profile, title, subtitle, display, kind) in enumerate(presets):
            history, call, _ = scenario(random.Random(42 + index), f"web_{batch}_{key}", profile, at)
            if key == "hospital":
                history = [h.model_copy(update={"caller_identity_verified": True}) for h in history]
                call = call.model_copy(update={"caller_identity_verified": True})
            self.store.ingest(history)
            if key == "hospital":
                add_demo_privilege(self.store, call.caller, "Городская больница · демо")
            call = call.model_copy(update={"started_at": utcnow()})
            items.append({"id": key, "title": title, "subtitle": subtitle, "display_caller": display,
                          "display_callee": "+7 903 ***-**-07" if key == "personal" else "+7 916 ***-**-83",
                          "kind": kind, "call": call.model_dump(mode="json")})
        emergency = {**items[0]["call"], "call_id": f"web_{batch}_emergency", "callee": "103"}
        items.append({"id": "emergency", "title": "Вызов скорой помощи", "subtitle": "Экстренный маршрут важнее оценки риска",
                      "display_caller": items[0]["display_caller"], "display_callee": "103", "kind": "protected", "call": emergency})
        spoof = {**items[3]["call"], "call_id": f"web_{batch}_spoof", "ingress_trunk": "unknown_trunk",
                 "caller_identity_verified": False}
        items.append({"id": "spoof", "title": "Подмена номера больницы", "subtitle": "Тот же номер, неподтверждённый источник",
                      "display_caller": items[3]["display_caller"], "display_callee": "+7 916 ***-**-83", "kind": "mixed", "call": spoof})
        return items
