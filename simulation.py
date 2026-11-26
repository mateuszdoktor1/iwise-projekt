"""Odtwarzanie VOD z jednym pobieranym segmentem i odcinkowo stałym łączem."""

from dataclasses import dataclass
from itertools import pairwise
from math import inf, isfinite
from statistics import mean

from fis import BUFFER_MAX, RATES, available_rate, infer

SEGMENT_SECONDS = 4.0
SEGMENTS = 45  # 3 minuty filmu
# (początek przedziału czasu ściennego [s], przepustowość [Mb/s]).
# Ostatnia wartość obowiązuje do końca odtwarzania.
PROFILES = {
    "stabilne": [(0, 6.0)],
    "spadek": [(0, 6.0), (37, 0.8), (82, 6.0)],
    "wahania": [(9 * i, (2.4, 3.2)[i % 2]) for i in range(23)],
}


def download_time(profile, start, megabits):
    """Przenieś dane, rozliczając ilość pobraną po obu stronach każdej zmiany łącza."""
    remaining = megabits
    now = start
    for (_, speed), (end, _) in pairwise([*profile, (inf, 0)]):
        if end <= now:
            continue
        capacity = (end - now) * speed
        if remaining <= capacity:
            return now - start + remaining / speed
        remaining -= capacity
        now = end
    raise ValueError("Profil musi kończyć się dodatnią przepustowością.")


def threshold_rate(throughput, buffer):
    chosen = available_rate(0.8 * throughput)
    if buffer <= 4:
        return RATES[max(0, RATES.index(chosen) - 1)]
    return chosen


POLICIES = {
    "FIS": lambda throughput, buffer: infer(throughput, buffer).rate,
    "Próg": threshold_rate,
    "Stałe 2": lambda throughput, buffer: 2.0,
}


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    buffer_before: float
    buffer_after: float
    estimated_speed: float | None
    rate: float
    stall: float


def validate_profile(profile):
    if (not profile or profile[0][0] != 0
            or any(not isfinite(t) or not isfinite(speed) or speed <= 0 for t, speed in profile)
            or any(a[0] >= b[0] for a, b in pairwise(profile))):
        raise ValueError("Pierwszy czas musi wynosić 0 s, kolejne muszą ściśle rosnąć, "
                         "a przepustowości muszą być dodatnie. Podaj skończone liczby.")


def simulate(profile, policy, count=SEGMENTS):
    """Strategia widzi tylko ostatni pomiar i zapas dostępny przed wysłaniem żądania."""
    validate_profile(profile)
    if count < 1:
        raise ValueError("Film powinien zawierać co najmniej jeden segment.")
    now = buffer = 0.0
    estimate = None
    log = []
    for _ in range(count):
        wait = max(0.0, buffer - BUFFER_MAX)
        now += wait
        buffer -= wait
        rate = RATES[0] if estimate is None else policy(estimate, buffer)
        size = rate * SEGMENT_SECONDS
        duration = download_time(profile, now, size)
        # Pierwszy segment inicjuje odtwarzanie. Start liczymy osobno od zacięć.
        stall = 0.0 if estimate is None else max(0.0, duration - buffer)
        after = max(0.0, buffer - duration) + SEGMENT_SECONDS
        log.append(Segment(now, now + duration, buffer, after, estimate, rate, stall))
        estimate = size / duration
        now += duration
        buffer = after
    return log


def metrics(log):
    return {
        "start_s": log[0].end,
        "zatrzymania_s": sum(s.stall for s in log),
        "srednia_Mb_s": mean(s.rate for s in log),
        "zmiany": sum(a.rate != b.rate for a, b in pairwise(log)),
    }
