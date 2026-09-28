from datetime import timedelta
import json
import math
from pathlib import Path
import random

from fastapi.testclient import TestClient
import numpy as np
from pydantic import ValidationError
import pytest

from antifraud.api import create_app
from antifraud.features import extract_features, FEATURE_NAMES
from antifraud.generate import scenario
from antifraud.model import RiskModel
from antifraud.schemas import Approval, CallStart, CompletedCall, NumberQuery, PrivilegeRequest, normalize_number
from antifraud.service import ScoringService
from antifraud.storage import Store, utcnow
from antifraud.train import select_threshold


@pytest.fixture
def setup(tmp_path):
    at = utcnow()
    history, call, _ = scenario(random.Random(3), "fixture", "fraud_mass_dial", at)
    store = Store(tmp_path / "state.sqlite3")
    store.ingest(history)
    model = RiskModel({"feature_names": FEATURE_NAMES, "mean": [0.] * len(FEATURE_NAMES),
                       "scale": [1.] * len(FEATURE_NAMES), "coef": [.1] * len(FEATURE_NAMES),
                       "intercept": 4., "review_threshold": .8, "version": "test"})
    return store, model, call, history


@pytest.mark.parametrize("destination", ["101", "102", "103", "104", "112"])
def test_emergency_ignores_unavailable_database_and_model(setup, destination):
    _, _, call, _ = setup

    class Broken:
        def __getattr__(self, _):
            raise AssertionError("Emergency route must not access DB or model")

    engine = ScoringService(Broken(), Broken())
    result = engine.score_call(call.model_copy(update={"callee": destination}))
    assert result["action"] == "allow" and result["auto_block"] is False
    assert result["risk_score"] is None and result["protection"]["kind"] == "emergency_destination"


def test_operator_emergency_route_flag(setup):
    store, model, call, _ = setup
    result = ScoringService(store, model).score_call(call.model_copy(update={"destination_service": "emergency"}))
    assert result["protection"]["kind"] == "emergency_destination"


@pytest.mark.parametrize("callee", ["+74950000103", "+71030000000", "test:103", "911"])
def test_no_emergency_substring_match(setup, callee):
    store, model, call, _ = setup
    result = ScoringService(store, model).score_call(call.model_copy(update={"callee": callee}))
    assert result["status"] == "scored" and result["protection"] is None


def approve(store, call):
    request = store.request("hospital", PrivilegeRequest(number=call.caller, justification="Проверенный номер больницы"))
    approval = Approval(verified_subscriber_id=call.subscriber_id, verified_operator=call.source_operator,
                        verified_trunk=call.ingress_trunk, evidence_reference="Ownership-check-001",
                        expires_at=utcnow() + timedelta(days=2))
    store.approve(request["id"], approval)
    return request, approval


def test_pending_request_gives_no_privilege(setup):
    store, model, call, _ = setup
    store.request("hospital", PrivilegeRequest(number=call.caller, justification="Проверенный номер больницы"))
    assert ScoringService(store, model).score_call(call)["protection"] is None


def test_verified_callback_and_revoke(setup):
    store, model, call, _ = setup
    request, _ = approve(store, call)
    call = call.model_copy(update={"started_at": utcnow(), "caller_identity_verified": True})
    engine = ScoringService(store, model)
    assert engine.score_call(call)["protection"]["kind"] == "verified_social_organization"
    store.revoke(request["id"], "Номер больше не принадлежит больнице")
    assert engine.score_call(call)["protection"] is None
    actions = [r["action"] for r in store.audit_rows()]
    assert "privilege_approved" in actions and "privilege_revoked" in actions


@pytest.mark.parametrize("update", [{"caller_identity_verified": False}, {"ingress_trunk": "attacker"},
                                   {"subscriber_id": "attacker"}, {"source_operator": "attacker"}])
def test_caller_id_alone_is_not_privileged(setup, update):
    store, model, call, _ = setup
    approve(store, call)
    call = call.model_copy(update={"started_at": utcnow(), "caller_identity_verified": True, **update})
    assert ScoringService(store, model).score_call(call)["protection"] is None


def test_expired_privilege(setup):
    store, model, call, _ = setup
    _, approval = approve(store, call)
    call = call.model_copy(update={"started_at": approval.expires_at, "caller_identity_verified": True})
    assert ScoringService(store, model).score_call(call)["protection"] is None


def test_privilege_cannot_retroactively_protect_old_call(setup):
    store, model, call, _ = setup
    approve(store, call)
    assert ScoringService(store, model).score_call(call)["protection"] is None


def test_declining_and_invalid_approval(setup):
    store, _, call, _ = setup
    request, approval = approve(store, call)
    with pytest.raises(ValueError):
        store.approve(request["id"], approval)
    with pytest.raises(ValueError):
        store.approve(request["id"], approval.model_copy(update={"expires_at": utcnow() - timedelta(days=1)}))


def test_model_failure_is_fail_open(setup):
    store, model, call, _ = setup
    class Broken:
        def predict(self, _):
            raise RuntimeError("simulated model fault")
    for unavailable in (None, Broken()):
        result = ScoringService(store, unavailable).score_call(call)
        assert result["action"] == "allow" and result["status"] == "degraded"
        assert result["risk_score"] is None and not result["auto_block"]


def test_explanations_exactly_reconstruct_score(setup):
    store, model, call, _ = setup
    r = ScoringService(store, model).score_call(call)
    z = r["baseline_log_odds"] + sum(f["log_odds_contribution"] for f in r["factors"])
    assert math.isclose(z, r["total_log_odds"], abs_tol=1e-12)
    assert round(100/(1+math.exp(-z)), 2) == r["risk_score"]
    assert not r["auto_block"]


def test_future_and_late_cdrs_do_not_leak(setup):
    _, _, call, history = setup
    original = extract_features(history, call)
    late = history[0].model_copy(update={"call_id": "late", "observed_at": call.started_at + timedelta(seconds=1)})
    future = history[0].model_copy(update={"call_id": "future", "started_at": call.started_at + timedelta(seconds=1),
                                        "ended_at": call.started_at + timedelta(seconds=2), "observed_at": call.started_at + timedelta(seconds=3)})
    assert extract_features(history + [late, future], call) == original


def test_expired_history_and_current_call_excluded(setup):
    _, _, call, history = setup
    old = history[0].model_copy(update={"started_at": call.started_at - timedelta(days=2)})
    current = history[0].model_copy(update={"call_id": call.call_id})
    assert extract_features([old, current], call)[1] == 0


def test_history_is_idempotent_and_conflicts_roll_back(setup):
    store, _, call, history = setup
    assert store.ingest(history) == 0
    new = history[0].model_copy(update={"call_id": "new"})
    changed = history[0].model_copy(update={"destination_region": "other"})
    with pytest.raises(ValueError):
        store.ingest([new, changed])
    assert all(h.call_id != "new" for h in store.history(call.started_at))


def test_cold_number_is_unknown_not_safe(setup):
    store, model, _, _ = setup
    result = ScoringService(store, model).score_number(NumberQuery(number="test:unknown", at=utcnow()))
    assert result["status"] == "insufficient_data" and result["risk_score"] is None


def test_number_scoring(setup):
    store, model, call, _ = setup
    result = ScoringService(store, model).score_number(NumberQuery(number=call.caller, at=call.started_at))
    assert result["status"] == "scored" and 0 <= result["risk_score"] <= 100


def test_graph_detects_coordinated_numbers():
    history, call, _ = scenario(random.Random(4), "fanout", "fraud_fanout", utcnow())
    features, _ = extract_features(history, call)
    assert features["subscriber_numbers_24h"] == 4
    assert features["fanout_pattern"] > .5


@pytest.mark.parametrize("invalid", ["103abc", "tel:103", "00103", "１１２", "+7bad"])
def test_phone_validation(invalid):
    with pytest.raises(ValueError):
        normalize_number(invalid)


def test_schema_forbids_transcripts_and_post_call_fields(setup):
    _, _, call, history = setup
    for extra in ({"transcript": "secret"}, {"duration_seconds": 5}, {"privileged": True}):
        with pytest.raises(ValidationError):
            CallStart.model_validate({**call.model_dump(), **extra})
    with pytest.raises(ValidationError):
        CompletedCall.model_validate({**history[0].model_dump(), "duration_seconds": -1})
    with pytest.raises(ValidationError):
        CallStart.model_validate({**call.model_dump(), "started_at": "2026-01-01T00:00:00"})


def test_threshold_uses_fpr_budget():
    y = np.array([0, 0, 0, 1, 1])
    scores = np.array([.2, .4, .8, .7, .9])
    threshold = select_threshold(y, scores, max_fpr=0)
    assert threshold == .9
    assert np.mean((scores >= threshold)[y == 0]) == 0


def test_api_role_boundaries_and_workflow(setup):
    store, model, call, history = setup
    keys = {"operator": "o"*32, "admin": "a"*32, "organizations": {"hospital": "h"*32}}
    app = create_app(store, model, keys)
    with TestClient(app) as client:
        assert client.get("/health").json()["auto_block"] is False
        assert client.post("/v1/calls/score", json=call.model_dump(mode="json")).status_code == 401
        assert client.post("/v1/calls/score", json=call.model_dump(mode="json"), headers={"X-API-Key": "h"*32}).status_code == 401
        response = client.post("/v1/calls/score", json=call.model_dump(mode="json"), headers={"X-API-Key": "o"*32})
        assert response.status_code == 200 and response.json()["status"] == "scored"
        req = client.post("/v1/privileges/requests", json={"number": call.caller, "justification": "Проверить номер больницы"}, headers={"X-API-Key": "h"*32})
        assert req.status_code == 201 and req.json()["organization"] == "hospital"
        rid = req.json()["id"]
        body = {"verified_subscriber_id": call.subscriber_id, "verified_operator": call.source_operator,
                "verified_trunk": call.ingress_trunk, "evidence_reference": "ownership-test",
                "expires_at": (utcnow()+timedelta(days=1)).isoformat()}
        assert client.post(f"/v1/admin/privileges/{rid}/approve", json=body, headers={"X-API-Key": "h"*32}).status_code == 401
        assert client.post(f"/v1/admin/privileges/{rid}/approve", json=body, headers={"X-API-Key": "a"*32}).status_code == 200
        assert client.post("/v1/history", json=[history[0].model_dump(mode="json")], headers={"X-API-Key": "o"*32}).json()["inserted"] == 0
        assert client.get("/v1/admin/audit", headers={"X-API-Key": "a"*32}).status_code == 200


def test_role_keys_must_be_distinct(setup):
    store, model, _, _ = setup
    with pytest.raises(ValueError):
        create_app(store, model, {"operator": "x"*32, "admin": "x"*32, "organizations": {}})


def test_dataset_split_has_disjoint_owners_and_time_ranges():
    path = Path("data/queries.jsonl")
    if not path.exists():
        pytest.skip("Generate data to verify the bundled dataset")
    groups = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        groups.setdefault(row["split"], []).append(CallStart.model_validate(row["call"]))
    for left, right in (("train", "validation"), ("validation", "test"), ("train", "test")):
        assert not {c.subscriber_id for c in groups[left]} & {c.subscriber_id for c in groups[right]}
        assert max(c.started_at for c in groups[left]) < min(c.started_at for c in groups[right])
