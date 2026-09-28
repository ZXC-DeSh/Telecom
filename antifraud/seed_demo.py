"""Load current demo CDRs and write ready-to-send requests. No external telephony."""
import json
import os
from pathlib import Path
import random

from .generate import scenario
from .storage import Store, utcnow


def seed():
    path = Path(os.getenv("ANTIFRAUD_DB", "runtime/antifraud.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    store = Store(path)
    now = utcnow()
    requests = {}
    for i, name in enumerate(("personal", "fraud_mass_dial", "fraud_fanout", "hospital", "fraud_low_volume")):
        # Unique batch IDs keep repeat seeding idempotency conflicts out of the way.
        group = f"live_{int(now.timestamp()*1000000)}_{i}"
        history, call, _ = scenario(random.Random(42+i), group, name, now)
        store.ingest(history)
        requests[name] = call.model_dump(mode="json")
    requests["emergency_103"] = {**requests["fraud_mass_dial"], "call_id": "demo_emergency", "callee": "103"}
    Path("runtime").mkdir(exist_ok=True)
    Path("runtime/demo_requests.json").write_text(json.dumps(requests, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Demo CDRs loaded. Requests: runtime/demo_requests.json")


if __name__ == "__main__":
    seed()
