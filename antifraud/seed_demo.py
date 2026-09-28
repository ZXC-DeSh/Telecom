"""Загружаем синтетическую историю и сохраняем готовые запросы без обращения к телефонной сети."""
import json
from pathlib import Path
import random

from .generate import scenario
from .storage import Store, utcnow


def seed():
    path = Path(__file__).resolve().parents[1] / "runtime" / "antifraud.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    store = Store(path)
    now = utcnow()
    requests = {}
    for i, name in enumerate(("personal", "fraud_mass_dial", "fraud_fanout", "hospital", "fraud_low_volume")):
        # Уникальные идентификаторы пачек предотвращают конфликты при повторной подготовке примеров.
        group = f"live_{int(now.timestamp()*1000000)}_{i}"
        history, call, _ = scenario(random.Random(42+i), group, name, now)
        store.ingest(history)
        requests[name] = call.model_dump(mode="json")
    requests["emergency_103"] = {**requests["fraud_mass_dial"], "call_id": "demo_emergency", "callee": "103"}
    Path("runtime").mkdir(exist_ok=True)
    Path("runtime/demo_requests.json").write_text(json.dumps(requests, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Демонстрационные вызовы загружены. Запросы: runtime/demo_requests.json")


if __name__ == "__main__":
    seed()
