"""Dwuwejściowy sterownik Mamdaniego. Jednostki: Mb/s i sekundy."""

from dataclasses import dataclass

import numpy as np


RATES = (0.5, 1.0, 2.0, 4.0)
SPEED_ANCHORS = (1.0, 3.0, 5.0)
BUFFER_ANCHORS = (4.0, 8.0, 12.0)
SPEED_MAX = 8.0
BUFFER_MAX = 16.0  # w chwili wyboru segmentu
SPEED_LABELS = ("niska", "średnia", "wysoka")
BUFFER_LABELS = ("mały", "średni", "duży")
RATE_LABELS = ("niska", "umiarkowana", "wysoka", "bardzo wysoka")
# Wiersze: bufor. Kolumny: oszacowana przepustowość. Wartość: środek konsekwencji.
RULES = np.array([[0.5, 1, 1], [0.5, 2, 2], [0.5, 2, 4]])

HALF_WIDTH = 0.25
OUTPUT_AXIS = np.linspace(RATES[0] - HALF_WIDTH, RATES[-1] + HALF_WIDTH, 401)
OUTPUT_SETS = np.array([
    np.maximum(0, 1 - np.abs(OUTPUT_AXIS - center) / HALF_WIDTH)
    for center in RATES
])


def memberships(value, anchors):
    """Dwa zbiory brzegowe i trójkąt. Także na krańcach suma wynosi 1."""
    low, middle, high = anchors
    left = np.clip((middle - value) / (middle - low), 0, 1)
    right = np.clip((value - middle) / (high - middle), 0, 1)
    return np.array([left, 1 - left - right, right])


def available_rate(target):
    """Najwyższy dostępny wariant poniżej celu (tolerancja błędu centroidu)."""
    return max((rate for rate in RATES if rate <= target + 1e-10), default=RATES[0])


@dataclass
class Decision:
    strengths: np.ndarray
    aggregate: np.ndarray
    target: float
    rate: float


def infer(throughput, buffer):
    if not np.isfinite(throughput) or throughput < 0:
        raise ValueError("Przepustowość musi być skończona i nieujemna.")
    if not np.isfinite(buffer) or not 0 <= buffer <= BUFFER_MAX:
        raise ValueError(f"Bufor w chwili decyzji musi należeć do [0, {BUFFER_MAX:g}] s.")
    # Ostatni zbiór brzegowy nasyca się także przy pomiarze ponad skalą modelu.
    speed_mu = memberships(min(throughput, SPEED_MAX), SPEED_ANCHORS)
    buffer_mu = memberships(buffer, BUFFER_ANCHORS)
    strengths = np.outer(buffer_mu, speed_mu)  # AND przez iloczyn
    aggregate = np.zeros_like(OUTPUT_AXIS)
    for center, shape in zip(RATES, OUTPUT_SETS):
        # Skalowanie zbioru siłą reguły i sumowanie wkładów o tej samej konsekwencji.
        aggregate += strengths[RULES == center].sum() * shape
    area = np.trapezoid(aggregate, OUTPUT_AXIS)
    target = float(np.trapezoid(OUTPUT_AXIS * aggregate, OUTPUT_AXIS) / area)
    return Decision(strengths, aggregate, target, available_rate(target))
