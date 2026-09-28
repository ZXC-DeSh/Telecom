from collections import defaultdict
from datetime import timedelta
import math

import networkx as nx

from .schemas import CallStart, CompletedCall


FEATURE_LABELS = {
    "calls_1h": "Количество завершённых вызовов за час",
    "unique_callees_1h": "Уникальные адресаты за час",
    "regions_1h": "Охват регионов за час",
    "short_ratio_24h": "Доля коротких отвеченных вызовов за сутки",
    "unanswered_ratio_24h": "Доля неотвеченных вызовов за сутки",
    "first_second_ratio_24h": "Доля завершений в первую секунду",
    "mean_duration_24h": "Средняя длительность отвеченных вызовов",
    "repeat_contact_ratio_24h": "Доля повторных контактов",
    "subscriber_numbers_24h": "Номеров одного абонента в наблюдаемом графе",
    "fanout_pattern": "Согласованный обзвон непересекающихся списков",
    "foreign_ingress": "Вход из-за рубежа относительно домашней сети",
    "voip": "Тип соединения VoIP",
    "unverified_identity": "Источник не подтверждён оператором",
    "hour_sin_utc": "Время UTC циклическая компонента sin",
    "hour_cos_utc": "Время UTC циклическая компонента cos",
}
FEATURE_NAMES = list(FEATURE_LABELS)


def eligible_history(history: list[CompletedCall], call: CallStart) -> list[CompletedCall]:
    lower = call.started_at - timedelta(hours=24)
    return [h for h in history if lower <= h.started_at < call.started_at
            and h.observed_at <= call.started_at and h.call_id != call.call_id]


def extract_features(history: list[CompletedCall], call: CallStart, home_country="RU"):
    """Признаки на момент оценки: будущие, незавершённые и ещё не полученные записи исключаются."""
    prior = eligible_history(history, call)
    own = [h for h in prior if h.caller == call.caller
           and h.subscriber_id == call.subscriber_id]
    hour = [h for h in own if h.started_at >= call.started_at - timedelta(hours=1)]
    answered = [h for h in own if h.answered]
    graph = nx.DiGraph()
    owners = nx.Graph()
    by_number = defaultdict(list)
    for h in prior:
        graph.add_edge(("number", h.caller), ("number", h.callee))
        # Используем устойчивые псевдонимные идентификаторы абонентов из данных оператора.
        owners.add_edge(("subscriber", h.subscriber_id), ("number", h.caller))
        if h.subscriber_id == call.subscriber_id:
            by_number[h.caller].append(h)
    owner = ("subscriber", call.subscriber_id)
    numbers = list(owners.neighbors(owner)) if owner in owners else []
    active = [n[1] for n in numbers if len(by_number[n[1]]) >= 5]
    fanout = 0.0
    if len(active) >= 3:
        targets = [set(graph.successors(("number", n))) for n in active]
        total_targets = sum(map(len, targets))
        disjointness = len(set.union(*targets)) / max(total_targets, 1)
        means = [sum(h.duration_seconds for h in by_number[n]) / len(by_number[n]) for n in active]
        # Проверяем общий час активности и сходство длительностей, а не только разные списки адресатов.
        buckets = [{int(h.started_at.timestamp() // 3600) for h in by_number[n]} for n in active]
        synchronized = bool(set.intersection(*buckets))
        duration_similarity = 1 / (1 + (max(means) - min(means)) / 10)
        fanout = disjointness * duration_similarity * float(synchronized)
    n = len(own)
    values = {
        "calls_1h": len(hour),
        "unique_callees_1h": len({h.callee for h in hour}),
        "regions_1h": len({h.destination_region for h in hour}),
        "short_ratio_24h": sum(h.duration_seconds <= 10 for h in answered) / max(len(answered), 1),
        "unanswered_ratio_24h": sum(not h.answered for h in own) / max(n, 1),
        "first_second_ratio_24h": sum((h.ended_at - h.started_at).total_seconds() <= 1 for h in own) / max(n, 1),
        "mean_duration_24h": sum(h.duration_seconds for h in answered) / max(len(answered), 1),
        "repeat_contact_ratio_24h": 1 - len({h.callee for h in own}) / n if n else 0,
        "subscriber_numbers_24h": len(numbers),
        "fanout_pattern": fanout,
        "foreign_ingress": float(call.source_country != home_country),
        "voip": float(call.connection_type == "voip"),
        "unverified_identity": float(not call.caller_identity_verified),
        "hour_sin_utc": math.sin(2 * math.pi * (call.started_at.timestamp() % 86400) / 86400),
        "hour_cos_utc": math.cos(2 * math.pi * (call.started_at.timestamp() % 86400) / 86400),
    }
    return {k: float(values[k]) for k in FEATURE_NAMES}, n
