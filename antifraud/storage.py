from datetime import datetime, timezone
from contextlib import contextmanager
import sqlite3
from uuid import uuid4

from .schemas import Approval, CallStart, CompletedCall, PrivilegeRequest


def utcnow():
    return datetime.now(timezone.utc)


class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS calls (
                    call_id TEXT PRIMARY KEY, started REAL NOT NULL,
                    observed REAL NOT NULL, body TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS calls_time ON calls(started, observed);
                CREATE TABLE IF NOT EXISTS privileges (
                    id TEXT PRIMARY KEY, organization TEXT NOT NULL, number TEXT NOT NULL,
                    status TEXT NOT NULL, requested REAL NOT NULL, approved REAL,
                    expires REAL, body TEXT NOT NULL, approval TEXT);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def ingest(self, calls: list[CompletedCall]):
        count = 0
        with self.connect() as db:
            for call in calls:
                body = call.model_dump_json()
                old = db.execute("SELECT body FROM calls WHERE call_id=?", (call.call_id,)).fetchone()
                if old:
                    if old["body"] != body:
                        raise ValueError("Уже существует другая запись с таким идентификатором вызова")
                    continue
                db.execute("INSERT INTO calls VALUES(?,?,?,?)", (call.call_id, call.started_at.timestamp(),
                           call.observed_at.timestamp(), body))
                count += 1
        return count

    def history(self, at: datetime):
        with self.connect() as db:
            rows = db.execute("SELECT body FROM calls WHERE started >= ? AND started < ? AND observed <= ?",
                              (at.timestamp() - 86400, at.timestamp(), at.timestamp())).fetchall()
        return [CompletedCall.model_validate_json(r["body"]) for r in rows]

    def request(self, org: str, request: PrivilegeRequest):
        request_id = str(uuid4())
        with self.connect() as db:
            db.execute("INSERT INTO privileges(id,organization,number,status,requested,body) VALUES(?,?,?,?,?,?)",
                       (request_id, org, request.number, "pending", utcnow().timestamp(), request.model_dump_json()))
        return {"id": request_id, "status": "pending", "organization": org, "number": request.number}

    def approve(self, request_id: str, approval: Approval):
        now = utcnow()
        if not now < approval.expires_at or (approval.expires_at - now).total_seconds() > 366 * 86400:
            raise ValueError("Срок привилегии должен быть в будущем и не превышать 366 дней")
        with self.connect() as db:
            row = db.execute("SELECT * FROM privileges WHERE id=?", (request_id,)).fetchone()
            if not row:
                raise KeyError(request_id)
            changed = db.execute("UPDATE privileges SET status='approved', approved=?, expires=?, approval=? WHERE id=? AND status='pending'",
                                 (now.timestamp(), approval.expires_at.timestamp(), approval.model_dump_json(), request_id)).rowcount
            if changed != 1:
                raise ValueError("Подтвердить можно только ещё не обработанную заявку")
        return {"id": request_id, "status": "approved"}

    def revoke(self, request_id: str, reason: str):
        with self.connect() as db:
            changed = db.execute("UPDATE privileges SET status='revoked' WHERE id=? AND status!='revoked'", (request_id,)).rowcount
            if not changed:
                raise KeyError(request_id)
        return {"id": request_id, "status": "revoked"}

    def protection(self, call: CallStart):
        # Отзыв применяется немедленно, в том числе при повторной оценке старого вызова.
        with self.connect() as db:
            rows = db.execute("SELECT * FROM privileges WHERE number=? AND status='approved' AND approved<=? AND expires>?",
                              (call.caller, call.started_at.timestamp(), call.started_at.timestamp())).fetchall()
        for row in rows:
            a = Approval.model_validate_json(row["approval"])
            if (call.caller_identity_verified
                    and call.subscriber_id == a.verified_subscriber_id
                    and call.source_operator == a.verified_operator
                    and call.ingress_trunk == a.verified_trunk):
                return {"kind": "verified_social_organization", "organization": row["organization"],
                        "registry_id": row["id"], "reason": "Подтверждённый обратный звонок общественно важной организации"}
        return None

    def list_requests(self, org=None):
        with self.connect() as db:
            if org:
                rows = db.execute("SELECT id,organization,number,status,requested,expires FROM privileges WHERE organization=?", (org,)).fetchall()
            else:
                rows = db.execute("SELECT id,organization,number,status,requested,expires FROM privileges").fetchall()
        return [dict(r) for r in rows]
