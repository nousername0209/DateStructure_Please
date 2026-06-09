"""One-off generator for assets/data/profiles.json.

Builds ~150 profiles from a fixed list of Korean names, randomly assigning
hobbies and home cities. City assignment is intentionally *not* uniform: it is
weighted toward the capital region / large metros to match the lopsided
distribution implied by the expanded world_map.json. Run from the repo root:

    python scripts/gen_profiles.py
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

BOYS = [
    "Minjun", "Jihun", "Hyeonu", "Junseo", "Ujin", "Geonu", "Yejun", "Hyeonjun", "Donghyeon", "Dohyeon",
    "Junhyeok", "Minjae", "Seunghyeon", "Minseong", "Seungmin", "Seojun", "Junyeong", "Jiho", "Seonghyeon", "Siu",
    "Mingyu", "Jihwan", "Jeongu", "Junu", "Seongmin", "Seojin", "Jiwon", "Jinu", "Jimin", "Jihu",
    "Eunchan", "Hangyeol", "Jaemin", "Seungu", "Hyeonseo", "Jaewon", "Minhyeok", "Minseok", "Minseo", "Jaehyeon",
    "Jeongmin", "Doyun", "Junho", "Minu", "Jeonghyeon", "Yuchan", "Taehyeon", "Hyeonsu", "Minchan", "Seungjun",
    "Jiseong", "Gyeongmin", "Seongjun", "Yeonu", "Hyeonmin", "Jiu", "Juwon", "Jeonghun", "Eunseong", "Seonu",
    "Yunho", "Donggeon", "Yechan", "Jaeyun", "Sihu", "Gyumin", "Minsu", "Seungwon", "Jaehun", "Mingi",
    "Seongbin", "Junseong",
]

GIRLS = [
    "Seoyeon", "Minseo", "Jimin", "Seohyeon", "Seoyun", "Yeeun", "Haeun", "Subin", "Jiu", "Yujin",
    "Eunseo", "Minji", "Yunseo", "Yejin", "Jiyun", "Jiwon", "Seoyeong", "Yewon", "Sumin", "Gaeun",
    "Suyeon", "Chaewon", "Daeun", "Chaeeun", "Sua", "Yerin", "Hyeonseo", "Yubin", "Minju", "Jihyeon",
    "Soyeon", "Seojin", "Jieun", "Soyun", "Suhyeon", "Sieun", "Eunchae", "Nayeong", "Yunji", "Dayeon",
    "Yebin", "Yuna", "Nayeon", "Hyeonji", "Hyewon", "Jisu", "Yeji", "Mingyeong", "Nagyeong", "Eunji",
    "Yeseo", "Nahyeon", "Jiyeon", "Sujin", "Siyeon", "Dahyeon", "Yeonu", "Minjeong", "Sihyeon", "Jiyu",
    "Yuna", "Gayeon", "Yerim", "Gayeong", "Gahyeon", "Sohyeon", "Hayun", "Chaerin", "Yujeong", "Ayeong",
    "Gyuri", "Taehui", "Jiyeong", "Hayeong", "Doyeon", "Jueun", "Seeun",
]

HOBBIES = [
    "football", "basketball", "running", "jazz", "classic", "oil_painting", "painting",
]

# City *target counts* (sum to len(BOYS)+len(GIRLS) == 149). Capital region /
# big metros lean a bit higher, but the spread is gentle: max-min ~= 11, so the
# distribution is mildly uneven rather than lopsided. Assigned deterministically
# (then shuffled) so the per-city counts land exactly on these targets.
CITY_TARGETS = {
    "Seoul": 18, "Busan": 12, "Incheon": 11, "Daegu": 11, "Yongin": 10,
    "Daejeon": 10, "Suwon": 10, "Gwangju": 9, "Jeonju": 9, "Ulsan": 9,
    "Wonju": 9, "Pohang": 8, "Sejong": 8, "Jeju": 8, "Gangneung": 7,
}

TIERS = [("basic", 1), ("silver", 2), ("gold", 3)]
TIER_W = [55, 30, 15]  # most users basic, gold rare

START = datetime(2026, 1, 1, 8, 0, 0)
SPAN_DAYS = 159  # through 2026-06-09


def make_profile(idx: int, name: str, gender: str, city: str) -> dict:
    tier, priority = random.choices(TIERS, weights=TIER_W, k=1)[0]
    # success_rate loosely tracks tier, with spread
    base = {"basic": 0.30, "silver": 0.55, "gold": 0.78}[tier]
    success = round(min(0.97, max(0.12, random.gauss(base, 0.12))), 2)
    joined = START + timedelta(
        days=random.randint(0, SPAN_DAYS),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    return {
        "id": f"u{idx:03d}",
        "name": name,
        "gender": gender,
        "city": city,
        "hobby": random.choice(HOBBIES),
        "tier": tier,
        "tier_priority": priority,
        "success_rate": success,
        "suspicion": random.randint(2, 98),
        "joined_at": joined.strftime("%Y-%m-%dT%H:%M:%S"),
        "blacklist": [],
    }


def main() -> None:
    people = [(n, "male") for n in BOYS] + [(n, "female") for n in GIRLS]
    random.shuffle(people)  # interleave genders across ids

    # Deterministic city pool sized to the target counts, then shuffled so cities
    # scatter across ids while still hitting each target exactly.
    city_pool = [city for city, n in CITY_TARGETS.items() for _ in range(n)]
    assert len(city_pool) == len(people), (len(city_pool), len(people))
    random.shuffle(city_pool)

    profiles = [
        make_profile(i, name, g, city)
        for i, ((name, g), city) in enumerate(zip(people, city_pool), start=1)
    ]
    ids = [p["id"] for p in profiles]

    # A sprinkling of blacklist entries (mutual-ish avoidance).
    for p in random.sample(profiles, k=18):
        target = random.choice(ids)
        if target != p["id"]:
            p["blacklist"] = [target]

    # Generate a relationship graph over the new ids.
    kinds = ["best_friend", "ex_partner", "scam_partner"]
    kind_w = [45, 35, 20]
    seen: set[frozenset[str]] = set()
    relationships = []
    while len(relationships) < 60:
        a, b = random.sample(ids, 2)
        key = frozenset((a, b))
        if key in seen:
            continue
        seen.add(key)
        relationships.append(
            {"from": a, "to": b, "type": random.choices(kinds, weights=kind_w, k=1)[0]}
        )

    out = {"profiles": profiles, "relationships": relationships}
    path = Path("assets/data/profiles.json")
    with path.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Wrote {len(profiles)} profiles, {len(relationships)} relationships -> {path}")

    # quick distribution report
    from collections import Counter
    print("city:", dict(Counter(p["city"] for p in profiles)))
    print("tier:", dict(Counter(p["tier"] for p in profiles)))
    print("gender:", dict(Counter(p["gender"] for p in profiles)))


if __name__ == "__main__":
    main()
