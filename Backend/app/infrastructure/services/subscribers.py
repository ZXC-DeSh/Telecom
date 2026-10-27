from collections import defaultdict
from datetime import datetime

from app.domain.entities.subscriber import (
    SubscriberActivityPoint,
    SubscriberContact,
    SubscriberProfile,
    SubscriberStatistics,
)
from app.domain.value_objects import CallType, RiskLevel
from app.infrastructure.database.connection import Database
from app.infrastructure.database.query import Filter, Sort


class SubscriberService:
    def __init__(self, database: Database) -> None:
        self._database = database

    def get_profile(self, msisdn_a: str) -> SubscriberProfile | None:
        rows = self._database.select_all(
            "public.calls_with_latest_assessment",
            (
                "call_type",
                "msisdn_a",
                "msisdn_b",
                "call_time",
                "duration_seconds",
                "msisdn_c",
                "risk_score",
                "risk_level",
                "is_fraud",
            ),
            filters=(Filter("msisdn_a", "=", msisdn_a),),
            order_by=(Sort("call_time"), Sort("id")),
        )

        if not rows:
            return None

        subscriber_msisdn = msisdn_a
        contacts: dict[str, list[tuple[float | None, RiskLevel | None]]] = defaultdict(
            list
        )
        related_suspicious: set[str] = set()
        activity: dict[datetime, int] = defaultdict(int)
        incoming = outgoing = forwarded = short_calls = unanswered = 0
        risk_score: float | None = None
        risk_level: RiskLevel | None = None

        for (
            call_type_value,
            msisdn_a,
            msisdn_b,
            call_time,
            duration,
            msisdn_c,
            score,
            level,
            is_fraud,
        ) in rows:
            call_type = CallType(call_type_value)
            if call_type == CallType.INCOMING:
                incoming += 1
            elif call_type == CallType.OUTGOING:
                outgoing += 1
            else:
                forwarded += 1
            short_calls += duration < 10
            unanswered += duration == 0
            activity[call_time.replace(minute=0, second=0, microsecond=0)] += 1

            if score is not None and (risk_score is None or score > risk_score):
                risk_score = score
                risk_level = RiskLevel(level) if level is not None else None

            parties = {number for number in (msisdn_a, msisdn_b, msisdn_c) if number}
            parties.discard(subscriber_msisdn)
            for number in parties:
                contacts[number].append(
                    (score, RiskLevel(level) if level is not None else None)
                )
                if is_fraud or level in (
                    RiskLevel.HIGH.value,
                    RiskLevel.CRITICAL.value,
                ):
                    related_suspicious.add(number)

        total_calls = len(rows)
        contacts_result = tuple(
            SubscriberContact(
                msisdn=number,
                calls_count=len(call_risks),
                risk_score=max(
                    (score for score, _ in call_risks if score is not None),
                    default=None,
                ),
                risk_level=_level_for_max_score(call_risks),
            )
            for number, call_risks in sorted(
                contacts.items(), key=lambda item: (-len(item[1]), item[0])
            )
        )
        return SubscriberProfile(
            msisdn=subscriber_msisdn,
            statistics=SubscriberStatistics(
                total_calls=total_calls,
                incoming_calls=incoming,
                outgoing_calls=outgoing,
                forwarded_calls=forwarded,
                unique_contacts=len(contacts),
                short_calls=short_calls,
                unanswered_calls=unanswered,
                short_calls_ratio=short_calls / total_calls,
                unanswered_calls_ratio=unanswered / total_calls,
            ),
            first_seen_at=min(row[3] for row in rows),
            last_seen_at=max(row[3] for row in rows),
            risk_score=risk_score,
            risk_level=risk_level,
            contacts=contacts_result,
            activity=tuple(
                SubscriberActivityPoint(timestamp=timestamp, calls_count=count)
                for timestamp, count in sorted(activity.items())
            ),
            related_suspicious_numbers=tuple(sorted(related_suspicious)),
        )


def _level_for_max_score(
    call_risks: list[tuple[float | None, RiskLevel | None]],
) -> RiskLevel | None:
    scored = [(score, level) for score, level in call_risks if score is not None]
    if not scored:
        return None
    return max(scored, key=lambda item: item[0])[1]
