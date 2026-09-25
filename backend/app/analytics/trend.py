"""Trend detection on real report dates: bucketed counts + EWMA + CUSUM.

A trend is only claimed when a control-chart statistic crosses its limit. With too
little history the result is INSUFFICIENT_HISTORY - never a guessed direction.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

MIN_BUCKETS = 6
MIN_EVENTS = 10
LAMBDA = 0.3
EWMA_L = 2.7
CUSUM_K = 0.5
CUSUM_H = 4.0


def bucket_counts(dates: list[date], start: date, end: date, bucket_days: int) -> tuple[list[str], list[int]]:
    n = max(1, math.ceil(((end - start).days + 1) / bucket_days))
    counts = [0] * n
    first = end - timedelta(days=n * bucket_days - 1)
    for d in dates:
        idx = (d - first).days // bucket_days
        if 0 <= idx < n:
            counts[idx] += 1
    labels = [(first + timedelta(days=i * bucket_days)).isoformat() for i in range(n)]
    return labels, counts


def detect_trend(dates: list[date], start: date, end: date) -> dict[str, Any]:
    n_events = len(dates)
    span = (end - start).days + 1
    bucket_days = 7 if n_events >= 40 and span >= 7 * 16 else 30
    labels, counts = bucket_counts(dates, start, end, bucket_days)
    base = {"bucket": "week" if bucket_days == 7 else "month", "bucket_days": bucket_days, "labels": labels, "counts": counts, "n_events": n_events}
    if len(counts) < MIN_BUCKETS or n_events < MIN_EVENTS:
        return {**base, "trend": "INSUFFICIENT_HISTORY", "reason": f"Need >= {MIN_BUCKETS} periods and >= {MIN_EVENTS} occurrences (have {len(counts)} periods, {n_events} occurrences)"}

    recent_n = max(2, len(counts) // 4)
    baseline = counts[:-recent_n]
    recent = counts[-recent_n:]
    mu = sum(baseline) / len(baseline)
    var = sum((c - mu) ** 2 for c in baseline) / max(1, len(baseline) - 1)
    sigma = max(math.sqrt(var), math.sqrt(max(mu, 0.0)), 0.5)

    ewma: list[float] = []
    z = mu
    for c in counts:
        z = LAMBDA * c + (1 - LAMBDA) * z
        ewma.append(round(z, 4))
    width = EWMA_L * sigma * math.sqrt(LAMBDA / (2 - LAMBDA))
    ucl, lcl = mu + width, max(0.0, mu - width)

    cpos: list[float] = []
    cneg: list[float] = []
    sp = sn = 0.0
    for c in counts:
        sp = max(0.0, sp + (c - mu - CUSUM_K * sigma))
        sn = max(0.0, sn + (mu - c - CUSUM_K * sigma))
        cpos.append(round(sp, 4))
        cneg.append(round(sn, 4))
    h = CUSUM_H * sigma
    up = ewma[-1] > ucl or max(cpos[-recent_n:]) > h
    down = (lcl > 0 and ewma[-1] < lcl) or max(cneg[-recent_n:]) > h
    trend = "INCREASING" if up and not down else "DECREASING" if down and not up else "STABLE"
    recent_rate = sum(recent) / len(recent)
    return {
        **base,
        "trend": trend,
        "baseline_mean": round(mu, 3),
        "baseline_sigma": round(sigma, 3),
        "recent_mean": round(recent_rate, 3),
        "recent_periods": recent_n,
        "ewma": ewma,
        "ewma_lambda": LAMBDA,
        "ewma_ucl": round(ucl, 3),
        "ewma_lcl": round(lcl, 3),
        "cusum_pos": cpos,
        "cusum_neg": cneg,
        "cusum_k": CUSUM_K,
        "cusum_h": round(h, 3),
        "method": f"EWMA (lambda={LAMBDA}, L={EWMA_L}) and tabular CUSUM (k={CUSUM_K} sigma, h={CUSUM_H} sigma) against the baseline of the first {len(baseline)} {base['bucket']}s",
    }
