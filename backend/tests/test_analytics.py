from datetime import date, timedelta

from app.analytics.ranking import TOP_NOTE, _beta_prior, rank
from app.analytics.trend import detect_trend
from app.models import Pattern, PatternReport
from sqlalchemy import select


def test_trend_insufficient_history():
    today = date(2026, 9, 1)
    t = detect_trend([today - timedelta(days=3), today - timedelta(days=40)], today - timedelta(days=365), today)
    assert t["trend"] == "INSUFFICIENT_HISTORY"
    assert "reason" in t


def test_trend_detects_real_increase_and_stability():
    end = date(2026, 9, 1)
    start = end - timedelta(days=359)
    flat = [start + timedelta(days=d) for d in range(5, 360, 20)]  # ~1.5 per month, even
    assert detect_trend(flat, start, end)["trend"] == "STABLE"
    rising = flat + [end - timedelta(days=d) for d in range(0, 80, 5)]  # burst in the last months
    t = detect_trend(rising, start, end)
    assert t["trend"] == "INCREASING"
    assert t["cusum_h"] > 0 and len(t["ewma"]) == len(t["counts"])


def test_beta_prior_shrinks_small_groups():
    a, b = _beta_prior([1, 30, 20], [1, 100, 100])
    small_post = (1 + a) / (1 + a + b)
    assert small_post < 1.0  # 1/1 raw rate is pulled toward the dataset mean
    assert small_post < 0.6


def test_ranking_columns_and_language(db):
    r = rank(db, "site", days=365)
    assert r["items"]
    top = r["items"][0]
    for key in ("total_reports", "sif_potential_reports", "raw_rate", "raw_precursor_count", "eb_rate", "adjusted_score", "eb_rate_ci90"):
        assert key in top
    assert top["notes"][0] == TOP_NOTE
    assert "dangerous" not in str(r).lower()
    assert "EB-adjusted" in r["method"]["score"]
    act = rank(db, "activity", days=365)
    assert act["items"][0]["raw_density"] is None  # no exposure denominator for activities


def test_patterns_come_from_data(db):
    pats = db.scalars(select(Pattern).where(Pattern.is_current.is_(True))).all()
    assert pats, "pattern mining produced no patterns on the seeded data"
    for p in pats:
        members = db.scalars(select(PatternReport).where(PatternReport.pattern_id == p.id)).all()
        assert len(members) == p.occurrences
        assert sum(1 for v in p.signature.values() if v) >= 2
        assert p.trend in ("INCREASING", "DECREASING", "STABLE", "INSUFFICIENT_HISTORY")
        assert p.method in ("hdbscan", "frequency")
