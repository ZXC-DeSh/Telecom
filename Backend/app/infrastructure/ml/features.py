from collections.abc import Mapping
from datetime import timedelta

from app.domain.entities.call import Call
from app.domain.value_objects import CallType

SHORT_CALL_SECONDS = 10
LONG_CALL_SECONDS = 300
NIGHT_START_HOUR = 22
NIGHT_END_HOUR = 6
WINDOW_LENGTHS = {
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
}

FeatureValue = str | int | float | bool


def build_features(call: Call, history: tuple[Call, ...]) -> dict[str, FeatureValue]:
    a_history = tuple(item for item in history if item.msisdn_a == call.msisdn_a)
    b_history = tuple(item for item in history if item.msisdn_a == call.msisdn_b)
    features: dict[str, FeatureValue] = {
        "call_type": int(call.call_type.value),
        "duration_seconds": float(call.duration_seconds),
        "hour": call.call_time.hour,
        "day_of_week": call.call_time.weekday(),
        "is_weekend": call.call_time.weekday() >= 5,
        "is_night": call.call_time.hour >= NIGHT_START_HOUR
        or call.call_time.hour < NIGHT_END_HOUR,
        "is_short_call": call.duration_seconds <= SHORT_CALL_SECONDS,
        "is_zero_duration": call.duration_seconds == 0,
        "is_long_call": call.duration_seconds >= LONG_CALL_SECONDS,
        "cross_prefix_call": call.msisdn_a[:3] != call.msisdn_b[:3],
        "has_forwarding": call.msisdn_c is not None,
        "forwarding_chain_length_proxy": 2 if call.msisdn_c is not None else 1,
        "forwarding_chain_continuation_30s": _forwarding_continuation(call, history),
        "a_prior_unique_imsi_all_history": len(
            {item.imsi_a for item in a_history if item.imsi_a is not None}
        ),
        "a_prior_unique_contacts_all_history": len(
            {item.msisdn_b for item in a_history}
        ),
        "b_prior_unique_contacts_all_history": len(
            {item.msisdn_b for item in b_history}
        ),
    }

    a_contacts = _contacts_of(call.msisdn_a, history)
    b_contacts = _contacts_of(call.msisdn_b, history)
    reciprocal_contacts = {
        contact
        for contact in a_contacts
        if _has_contact(call.msisdn_a, contact, history)
        and _has_contact(contact, call.msisdn_a, history)
    }
    features.update(
        {
            "a_prior_graph_degree": len(a_contacts),
            "b_prior_graph_degree": len(b_contacts),
            "a_b_prior_reciprocal_contact": _has_contact(
                call.msisdn_a, call.msisdn_b, history
            )
            and _has_contact(call.msisdn_b, call.msisdn_a, history),
            "a_prior_reciprocal_contact_count": len(reciprocal_contacts),
            "a_prior_reciprocal_contact_rate": _ratio(
                len(reciprocal_contacts), len(a_contacts)
            ),
            "a_prior_forwarding_motif_repeats_7d": _forwarding_motif_repeats(
                call, history
            ),
            "a_b_prior_short_probe_then_long_call": call.duration_seconds
            >= LONG_CALL_SECONDS
            and any(
                item.msisdn_a == call.msisdn_a
                and item.msisdn_b == call.msisdn_b
                and _is_short(item)
                for item in history
            ),
        }
    )

    for window_name, window_length in WINDOW_LENGTHS.items():
        cutoff = call.call_time - window_length
        a_window = tuple(item for item in a_history if item.call_time >= cutoff)
        b_window = tuple(item for item in b_history if item.call_time >= cutoff)
        a_out = tuple(item for item in a_window if item.call_type == CallType.OUTGOING)
        a_in = tuple(item for item in a_window if item.call_type == CallType.INCOMING)
        a_short = tuple(item for item in a_window if _is_short(item))
        a_zero = tuple(item for item in a_window if item.duration_seconds == 0)
        a_long = tuple(item for item in a_window if _is_long(item))
        a_forwarded = tuple(
            item for item in a_window if item.call_type == CallType.FORWARDED
        )
        b_out = tuple(item for item in b_window if item.call_type == CallType.OUTGOING)
        b_in = tuple(item for item in b_window if item.call_type == CallType.INCOMING)
        b_callers = {
            item.msisdn_a
            for item in history
            if item.msisdn_b == call.msisdn_b and item.call_time >= cutoff
        }

        features.update(
            {
                f"a_calls_total_{window_name}": len(a_window),
                f"a_calls_out_{window_name}": len(a_out),
                f"a_calls_in_{window_name}": len(a_in),
                f"a_unique_contacts_out_{window_name}": len(
                    {item.msisdn_b for item in a_out}
                ),
                f"a_unique_contacts_in_{window_name}": len(
                    {item.msisdn_b for item in a_in}
                ),
                f"a_short_calls_{window_name}": len(a_short),
                f"a_short_call_rate_{window_name}": _ratio(len(a_short), len(a_window)),
                f"a_zero_calls_{window_name}": len(a_zero),
                f"a_zero_call_rate_{window_name}": _ratio(len(a_zero), len(a_window)),
                f"a_long_call_rate_{window_name}": _ratio(len(a_long), len(a_window)),
                f"a_forwarded_calls_{window_name}": len(a_forwarded),
                f"a_unique_imsis_{window_name}": len(
                    {item.imsi_a for item in a_window if item.imsi_a is not None}
                ),
                f"b_calls_total_{window_name}": len(b_window),
                f"b_calls_in_{window_name}": len(b_in),
                f"b_calls_out_{window_name}": len(b_out),
                f"b_unique_callers_{window_name}": len(b_callers),
                f"b_unique_contacts_out_{window_name}": len(
                    {item.msisdn_b for item in b_out}
                ),
            }
        )

    return features


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _is_short(call: Call) -> bool:
    return call.duration_seconds <= SHORT_CALL_SECONDS


def _is_long(call: Call) -> bool:
    return call.duration_seconds >= LONG_CALL_SECONDS


def _contacts_of(number: str, history: tuple[Call, ...]) -> set[str]:
    contacts: set[str] = set()
    for call in history:
        if call.msisdn_a == number:
            contacts.add(call.msisdn_b)
        if call.msisdn_b == number:
            contacts.add(call.msisdn_a)
        if call.msisdn_c == number:
            contacts.add(call.msisdn_b)
    contacts.discard(number)
    return contacts


def _has_contact(source: str, destination: str, history: tuple[Call, ...]) -> bool:
    return any(
        item.msisdn_a == source and item.msisdn_b == destination for item in history
    )


def _forwarding_motif_repeats(call: Call, history: tuple[Call, ...]) -> int:
    if call.msisdn_c is None:
        return 0
    cutoff = call.call_time - WINDOW_LENGTHS["7d"]
    return sum(
        1
        for item in history
        if item.call_time >= cutoff
        and item.call_type == CallType.FORWARDED
        and item.msisdn_a == call.msisdn_a
        and item.msisdn_b == call.msisdn_b
        and item.msisdn_c == call.msisdn_c
    )


def _forwarding_continuation(call: Call, history: tuple[Call, ...]) -> bool:
    lower_bound = call.call_time - timedelta(seconds=30)
    return any(
        item.call_type == CallType.FORWARDED
        and item.msisdn_c == call.msisdn_a
        and lower_bound <= item.call_time < call.call_time
        for item in history
    )


def validate_feature_contract(
    features: Mapping[str, FeatureValue], expected_names: tuple[str, ...]
) -> list[FeatureValue]:
    missing = set(expected_names).difference(features)
    if missing:
        raise ValueError(f"отсутствуют признаки модели: {', '.join(sorted(missing))}")
    return [features[name] for name in expected_names]
