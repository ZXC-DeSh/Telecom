"""Воспроизводимый генератор сценариев. Метки относятся к искусственным ситуациям, а не к реальным абонентам."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import random

from .features import extract_features
from .schemas import CallStart, CompletedCall

# Сценарий: метка, диапазон числа вызовов, средняя длительность, доля неответов, адресаты, регионы, число номеров.
SCENARIOS = {
    "personal": (0, (5, 18), 120, .12, 5, 2, 1),
    "courier": (0, (30, 70), 24, .30, 60, 3, 1),
    "hospital": (0, (45, 85), 32, .35, 90, 5, 4),
    "legitimate_call_center": (0, (55, 95), 42, .45, 100, 15, 4),
    "international_family": (0, (6, 20), 160, .15, 6, 3, 1),
    "busy_small_business": (0, (20, 55), 38, .27, 35, 7, 2),
    "short_legitimate_calls": (0, (25, 55), 9, .35, 40, 4, 1),
    "legitimate_notification": (0, (50, 90), 10, .55, 100, 14, 3),
    "fraud_mass_dial": (1, (45, 95), 8, .68, 130, 23, 2),
    "fraud_wangiri": (1, (40, 85), 1, .90, 110, 25, 1),
    "fraud_fanout": (1, (25, 55), 7, .66, 100, 21, 4),
    "fraud_low_volume": (1, (7, 23), 38, .38, 20, 9, 1),
}


def dump_line(file, value):
    file.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")


def scenario(rng, group, name, at):
    label, size_range, mean, unanswered, pool, regions, siblings = SCENARIOS[name]
    caller = f"test:{group}_n0"
    subscriber = f"sub_{group}"
    foreign = name == "international_family" or rng.random() < (.38 if label else .12)
    country = rng.choice(["DE", "KZ", "TR"]) if foreign else "RU"
    connection = rng.choices(["mobile", "fixed", "voip"], weights=[3, 2, 5])[0]
    verified = rng.random() < (.48 if label else .88)
    base = dict(subscriber_id=subscriber, source_country=country, source_operator="demo_operator",
                ingress_trunk="demo_trunk", connection_type=connection, caller_identity_verified=verified)
    history = []
    size = rng.randint(*size_range)
    # Перекрывающийся шум сохраняет сложные для различения легитимные и мошеннические случаи.
    mean *= rng.uniform(.5, 1.7)
    unanswered = max(.03, min(.98, unanswered + rng.uniform(-.15, .15)))
    for sibling in range(siblings):
        for j in range(size):
            age = rng.uniform(90, 3600 if size > 25 else 20000)
            start = at - timedelta(seconds=age)
            answered = rng.random() > unanswered
            duration = max(1, round(rng.expovariate(1 / mean), 1)) if answered else 0
            duration = min(duration, 70)
            ring = rng.uniform(4, 25) if name != "fraud_wangiri" else 1
            elapsed = duration + ring if answered else ring
            end = start + timedelta(seconds=elapsed)
            history.append(CompletedCall(
                **base, call_id=f"{group}_{sibling}_{j}", caller=f"test:{group}_n{sibling}",
                callee=f"test:{group}_recipient_{sibling}_{rng.randrange(pool)}",
                started_at=start, ended_at=end, observed_at=end + timedelta(seconds=2),
                duration_seconds=duration, answered=answered,
                destination_region=f"region_{rng.randrange(regions)}"))
    call = CallStart(**base, call_id=f"query_{group}", caller=caller, callee=f"test:{group}_new",
                     started_at=at, destination_region="region_1")
    return history, call, label


def generate(root=Path("data"), seed=42, counts=(600, 400, 400)):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    files = {name: (root / f"{name}.jsonl").open("w", encoding="utf-8")
             for name in ("calls", "queries", "labels", "features")}
    stats = {"seed": seed, "synthetic": True, "dialable": False, "calls": 0, "queries": 0, "splits": {}}
    try:
        for split_index, (split, count) in enumerate(zip(("train", "validation", "test"), counts)):
            stats["splits"][split] = {"queries": count, "fraud": 0, "benign": 0}
            for i in range(count):
                name = list(SCENARIOS)[i % len(SCENARIOS)]
                group = f"{split}_{i:05d}"
                # Абоненты, адресаты и временные периоды не пересекаются между выборками.
                at = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=split_index * 40, hours=i / 2)
                history, call, label = scenario(rng, group, name, at)
                for h in history:
                    dump_line(files["calls"], {"group_id": group, "split": split, "call": h.model_dump(mode="json")})
                dump_line(files["queries"], {"group_id": group, "split": split, "call": call.model_dump(mode="json")})
                dump_line(files["labels"], {"group_id": group, "split": split, "scenario": name, "label": label})
                features, n = extract_features(history, call)
                dump_line(files["features"], {"group_id": group, "split": split, "features": features, "history_calls": n})
                stats["calls"] += len(history)
                stats["queries"] += 1
                stats["splits"][split]["fraud" if label else "benign"] += 1
    finally:
        for f in files.values():
            f.close()
    (root / "manifest.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    generate(args.output, args.seed)
