"""
Data ingestion module.

Strategy:
1. Seeds a realistic set of NYC bus routes.
2. Pulls data from the NYC 311 Socrata Open Data API (no API key needed).
3. Maps 311 complaints to our schema and stores them in the DB.
4. If the API call fails or returns < 100 records, falls back to a synthetic
   data generator that produces realistic temporal complaint patterns.
"""
from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta

import requests

from backend.classifier import classify, map_311_complaint
from backend.database import SessionLocal
from backend.models import Feedback, Route, Trip

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NYC routes seed data
# ---------------------------------------------------------------------------
NYC_ROUTES: list[dict] = [
    {"route_number": "M15", "route_name": "1st/2nd Avenue", "borough": "Manhattan"},
    {"route_number": "M42", "route_name": "42nd Street Crosstown", "borough": "Manhattan"},
    {"route_number": "M86", "route_name": "86th Street Crosstown", "borough": "Manhattan"},
    {"route_number": "M104", "route_name": "Broadway", "borough": "Manhattan"},
    {"route_number": "M101", "route_name": "3rd/Lexington Avenue", "borough": "Manhattan"},
    {"route_number": "B41", "route_name": "Flatbush Avenue", "borough": "Brooklyn"},
    {"route_number": "B44", "route_name": "Nostrand Avenue", "borough": "Brooklyn"},
    {"route_number": "B63", "route_name": "5th Avenue Brooklyn", "borough": "Brooklyn"},
    {"route_number": "B6", "route_name": "Avenue J / Flatlands", "borough": "Brooklyn"},
    {"route_number": "B46", "route_name": "Utica Avenue", "borough": "Brooklyn"},
    {"route_number": "Q44", "route_name": "Jamaica / Flushing", "borough": "Queens"},
    {"route_number": "Q58", "route_name": "Myrtle Avenue", "borough": "Queens"},
    {"route_number": "Q17", "route_name": "Hillside Avenue", "borough": "Queens"},
    {"route_number": "Q23", "route_name": "Jamaica Avenue", "borough": "Queens"},
    {"route_number": "Q70", "route_name": "LaGuardia Express", "borough": "Queens"},
    {"route_number": "Bx12", "route_name": "Fordham Road", "borough": "Bronx"},
    {"route_number": "Bx19", "route_name": "Third Avenue", "borough": "Bronx"},
    {"route_number": "Bx41", "route_name": "Webster Avenue", "borough": "Bronx"},
    {"route_number": "Bx36", "route_name": "Tremont Avenue", "borough": "Bronx"},
    {"route_number": "Bx29", "route_name": "City Island / Pelham", "borough": "Bronx"},
    {"route_number": "S40", "route_name": "Richmond Terrace", "borough": "Staten Island"},
    {"route_number": "S78", "route_name": "Richmond Road", "borough": "Staten Island"},
]

# Realistic complaint comments per category
SYNTHETIC_COMMENTS: dict[str, list[str]] = {
    "Delays": [
        "Bus was 25 minutes late during rush hour again.",
        "Waited over 30 minutes at the stop. No communication about delays.",
        "The bus never showed up! Three passed in the other direction.",
        "Always running behind schedule on weekday mornings.",
        "The app said 5 minutes but I waited 40. Unacceptable.",
    ],
    "Crowding": [
        "The bus was so packed I couldn't even get on at my stop.",
        "People were practically standing on top of each other.",
        "No seats available, barely room to stand. Need more buses on this route.",
        "Rush hour is unbearable — sardine conditions every day.",
        "Couldn't board at all, bus was at full capacity.",
    ],
    "Cleanliness": [
        "Seats were covered in dirt and there was trash on the floor.",
        "The bus smelled terrible, clearly hadn't been cleaned.",
        "Graffiti all over the interior. Very unpleasant.",
        "Someone left garbage everywhere and it wasn't cleaned between trips.",
        "The windows were so dirty you couldn't see outside.",
    ],
    "Driver Behaviour": [
        "Driver was extremely rude when I asked about the route.",
        "The driver skipped the university stop without any announcement.",
        "Driver was on their phone for most of the trip — very dangerous.",
        "Aggressive driving, braking hard without warning.",
        "Driver refused to let passengers board even though there was space.",
    ],
    "Safety": [
        "There was a physical altercation on the bus and the driver ignored it.",
        "Felt very unsafe late at night — no working lights in the back.",
        "Witnessed harassment of another passenger with no response from driver.",
        "Emergency exit was blocked by packages — this is a safety violation.",
        "Driver ran two red lights. I was genuinely scared for my life.",
    ],
    "Mechanical Issues": [
        "Air conditioning wasn't working in 90°F heat — miserable trip.",
        "Bus broke down in the middle of the route, we all had to get off.",
        "Doors were malfunctioning — took 5 minutes just to open.",
        "The heater was stuck on full blast in summer.",
        "Engine was making a terrible noise the entire trip.",
    ],
    "Service Issues": [
        "Route was diverted without any notice posted at the stop.",
        "Stop was removed from the schedule but signs weren't updated.",
        "Schedule on the website is completely wrong for this route.",
        "Three buses came at once then nothing for an hour.",
        "The route was cancelled with no alternative offered.",
    ],
    "General": [
        "Decent ride overall but could use improvement.",
        "The trip was okay but the frequency needs to be better.",
        "Generally fine but the experience varies a lot day to day.",
        "Not terrible, not great. Average service.",
        "Would appreciate real-time tracking information at stops.",
    ],
}

# Category → typical overall rating range
CATEGORY_RATING_MAP: dict[str, tuple[float, float]] = {
    "Safety": (1.0, 2.0),
    "Driver Behaviour": (1.5, 2.5),
    "Mechanical Issues": (1.5, 2.5),
    "Delays": (1.5, 3.0),
    "Crowding": (2.0, 3.0),
    "Service Issues": (2.0, 3.5),
    "Cleanliness": (2.5, 3.5),
    "General": (3.0, 5.0),
}

# Hour-of-day weighting — rush hours have more complaints
HOUR_WEIGHTS: dict[int, float] = {
    0: 0.2, 1: 0.1, 2: 0.1, 3: 0.1, 4: 0.2,
    5: 0.5, 6: 1.5, 7: 3.0, 8: 3.5, 9: 2.0,
    10: 0.8, 11: 0.7, 12: 1.0, 13: 0.9, 14: 0.9,
    15: 1.2, 16: 2.0, 17: 3.5, 18: 3.0, 19: 2.0,
    20: 1.0, 21: 0.7, 22: 0.5, 23: 0.3,
}


def _weighted_hour() -> int:
    hours = list(HOUR_WEIGHTS.keys())
    weights = list(HOUR_WEIGHTS.values())
    return random.choices(hours, weights=weights, k=1)[0]


def _random_datetime(days_back: int = 180) -> datetime:
    delta = timedelta(
        days=random.randint(0, days_back),
        hours=_weighted_hour(),
        minutes=random.randint(0, 59),
    )
    return datetime.now() - delta


def seed_routes(db) -> dict[int, dict]:
    """Seed routes table and return {route_id: route_dict}."""
    existing = {r.route_number: r for r in db.query(Route).all()}
    route_map: dict[int, dict] = {}

    for r_data in NYC_ROUTES:
        if r_data["route_number"] not in existing:
            route = Route(**r_data)
            db.add(route)
            db.flush()
            route_map[route.id] = r_data
        else:
            r = existing[r_data["route_number"]]
            route_map[r.id] = r_data

    db.commit()
    return route_map


def generate_synthetic_feedback(db, route_map: dict[int, dict], count_per_route: int = 150):
    """Generate realistic synthetic feedback records for each route."""
    categories = list(SYNTHETIC_COMMENTS.keys())

    # Give some routes worse profiles (simulating problem routes)
    route_ids = list(route_map.keys())
    problem_routes = set(random.sample(route_ids, k=min(5, len(route_ids))))

    for route_id in route_ids:
        is_problem = route_id in problem_routes
        n = count_per_route + random.randint(-30, 30)

        for _ in range(n):
            # Problem routes skew toward negative categories
            if is_problem:
                category = random.choices(
                    categories,
                    weights=[5, 4, 3, 4, 3, 3, 3, 1],
                    k=1,
                )[0]
            else:
                category = random.choices(
                    categories,
                    weights=[1, 2, 2, 2, 1, 2, 2, 4],
                    k=1,
                )[0]

            comment = random.choice(SYNTHETIC_COMMENTS[category])
            result = classify(comment)

            low, high = CATEGORY_RATING_MAP.get(category, (2.5, 4.5))
            overall = round(random.uniform(low, high), 1)

            # Sub-ratings with some noise
            def jitter(base: float) -> float:
                return max(1.0, min(5.0, round(base + random.uniform(-0.8, 0.8), 1)))

            ts = _random_datetime(180)

            fb = Feedback(
                route_id=route_id,
                submitted_at=ts,
                hour_of_day=ts.hour,
                rating_overall=overall,
                rating_punctuality=jitter(overall) if category == "Delays" else jitter(overall + 0.3),
                rating_cleanliness=jitter(overall) if category == "Cleanliness" else jitter(overall + 0.5),
                rating_crowding=jitter(overall) if category == "Crowding" else jitter(overall + 0.4),
                rating_driver=jitter(overall) if category in ("Driver Behaviour", "Safety") else jitter(overall + 0.2),
                comment=comment,
                category=result["category"],
                severity=result["severity"],
                source="synthetic",
            )
            db.add(fb)

        # Add recent decline for some problem routes (to trigger deterioration detection)
        if is_problem:
            for _ in range(30):
                ts = datetime.now() - timedelta(days=random.randint(0, 29), hours=_weighted_hour())
                fb = Feedback(
                    route_id=route_id,
                    submitted_at=ts,
                    hour_of_day=ts.hour,
                    rating_overall=round(random.uniform(1.2, 2.3), 1),
                    rating_punctuality=round(random.uniform(1.0, 2.5), 1),
                    rating_cleanliness=round(random.uniform(1.5, 3.0), 1),
                    rating_crowding=round(random.uniform(1.0, 2.5), 1),
                    rating_driver=round(random.uniform(1.5, 2.8), 1),
                    comment=random.choice(SYNTHETIC_COMMENTS["Delays"] + SYNTHETIC_COMMENTS["Crowding"]),
                    category=random.choice(["Delays", "Crowding", "Driver Behaviour"]),
                    severity="medium",
                    source="synthetic",
                )
                db.add(fb)

    db.commit()
    logger.info("✅ Synthetic feedback generated.")


# ---------------------------------------------------------------------------
# NYC 311 Socrata API ingestion
# ---------------------------------------------------------------------------
SODA_ENDPOINT = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"

TRANSIT_COMPLAINT_TYPES = [
    "Bus", "Transit Noise", "Noise - Vehicle", "Blocked Bus Stop",
    "Obstructed Sidewalk at Bus Stop", "MTA Bus",
]


def fetch_311_data(limit: int = 3000) -> list[dict]:
    """Fetch MTA/transit-related 311 complaints from the Socrata API."""
    params = {
        "$limit": limit,
        "$order": "created_date DESC",
        "$where": (
            "agency='MTA' OR "
            "complaint_type='Bus' OR "
            "complaint_type='Blocked Bus Stop' OR "
            "complaint_type='Transit Noise'"
        ),
    }
    try:
        resp = requests.get(SODA_ENDPOINT, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"✅ Fetched {len(data)} records from NYC 311 API.")
        return data
    except Exception as e:
        logger.warning(f"⚠️  NYC 311 API fetch failed: {e}. Using synthetic data only.")
        return []


def ingest_311_records(db, records: list[dict], route_ids: list[int]):
    """Transform and insert 311 records into the feedback table."""
    if not records or not route_ids:
        return

    count = 0
    for rec in records:
        try:
            complaint_type = rec.get("complaint_type", "General")
            descriptor = rec.get("descriptor", "")
            created_raw = rec.get("created_date", "")

            if not created_raw:
                continue

            try:
                ts = datetime.strptime(created_raw[:19], "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                continue

            result = map_311_complaint(complaint_type, descriptor)
            low, high = CATEGORY_RATING_MAP.get(result["category"], (1.5, 3.5))
            overall = round(random.uniform(low, high), 1)

            def jitter(base: float) -> float:
                return max(1.0, min(5.0, round(base + random.uniform(-0.7, 0.7), 1)))

            fb = Feedback(
                route_id=random.choice(route_ids),
                submitted_at=ts,
                hour_of_day=ts.hour,
                rating_overall=overall,
                rating_punctuality=jitter(overall),
                rating_cleanliness=jitter(overall),
                rating_crowding=jitter(overall),
                rating_driver=jitter(overall),
                comment=f"{complaint_type}: {descriptor}"[:500],
                category=result["category"],
                severity=result["severity"],
                source="311_import",
            )
            db.add(fb)
            count += 1

        except Exception as exc:
            logger.debug(f"Skipping 311 record: {exc}")
            continue

    db.commit()
    logger.info(f"✅ Imported {count} records from NYC 311 data.")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def run_ingestion(synthetic_only: bool = False):
    """
    Full ingestion pipeline:
    1. Seed routes
    2. Attempt 311 API pull
    3. Supplement with synthetic data if needed
    """
    db = SessionLocal()
    try:
        # Check if already seeded
        existing_count = db.query(Feedback).count()
        if existing_count > 500:
            logger.info(f"Database already has {existing_count} feedback records. Skipping ingestion.")
            return

        logger.info("🚀 Starting data ingestion pipeline...")
        route_map = seed_routes(db)
        route_ids = list(route_map.keys())
        logger.info(f"✅ Seeded {len(route_ids)} routes.")

        if not synthetic_only:
            records = fetch_311_data(limit=2000)
            if records:
                ingest_311_records(db, records, route_ids)

        generate_synthetic_feedback(db, route_map, count_per_route=120)
        total = db.query(Feedback).count()
        logger.info(f"🎉 Ingestion complete. Total feedback records: {total}")

    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_ingestion()
