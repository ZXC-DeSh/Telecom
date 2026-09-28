"""Local demonstration without a network connection or any real phone numbers."""
from datetime import timedelta
import json
from pathlib import Path
import random
import tempfile

from .generate import scenario
from .model import RiskModel
from .schemas import Approval, NumberQuery, PrivilegeRequest
from .service import ScoringService
from .storage import Store, utcnow


def run():
    model = RiskModel.load("artifacts/model.json")
    output = []
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "demo.sqlite3")
        engine = ScoringService(store, model)
        now = utcnow()
        for i, name in enumerate(("personal", "fraud_mass_dial", "fraud_fanout", "hospital", "fraud_low_volume")):
            history, call, _ = scenario(random.Random(42+i), f"demo_{i}", name, now)
            store.ingest(history)
            output.append({"scenario": name, "result": engine.score_call(call)})
            if name == "hospital":
                request = store.request("demo_hospital", PrivilegeRequest(number=call.caller, justification="Демонстрационная заявка больницы"))
                store.approve(request["id"], Approval(verified_subscriber_id=call.subscriber_id,
                    verified_operator=call.source_operator, verified_trunk=call.ingress_trunk,
                    evidence_reference="DEMO ownership check", expires_at=now + timedelta(days=30)))
                verified = call.model_copy(update={"started_at": utcnow(), "caller_identity_verified": True})
                output.append({"scenario": "verified_hospital_callback", "result": engine.score_call(verified)})
                spoof = verified.model_copy(update={"ingress_trunk": "untrusted_trunk", "caller_identity_verified": False})
                output.append({"scenario": "spoofed_hospital", "result": engine.score_call(spoof)})
                store.revoke(request["id"], "Демонстрация отзыва привилегии")
                output.append({"scenario": "revoked_privilege", "result": engine.score_call(verified)})
        output.append({"scenario": "emergency_103", "result": engine.score_call(call.model_copy(update={"callee": "103"}))})
        output.append({"scenario": "number_assessment", "result": engine.score_number(NumberQuery(number=call.caller, at=now))})
        engine.model = None
        output.append({"scenario": "model_unavailable", "result": engine.score_call(call)})
    path = Path("artifacts/demo_results.json")
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    for row in output:
        r = row["result"]
        print(f"{row['scenario']}: score={r['risk_score']}, action={r['action']}, status={r['status']}")


if __name__ == "__main__":
    run()
