"""Zapis i odczyt profili łącza oraz ustawień strategii stałej."""

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from unicodedata import normalize

from fis import RATES
from simulation import DEFAULT_FIXED_RATE, PROFILES, validate_profile

PROFILE_DIR = Path(__file__).resolve().parent / "profile"


@dataclass(frozen=True)
class Profile:
    points: list[tuple[float, float]]
    fixed_rate: float = DEFAULT_FIXED_RATE


def profile_name(value):
    name = normalize("NFC", value.lower())
    if not name or not name[0].isalnum() or not all(c.isalnum() or c in "-_" for c in name):
        raise ValueError("Nazwa profilu musi zaczynać się literą lub cyfrą. "
                         "Dopuszczalne są litery, cyfry, łącznik i podkreślenie.")
    return name


def parse_points(tokens):
    points = []
    for token in tokens:
        try:
            time, speed = token.replace(",", ".").split(":")
            points.append((float(time), float(speed)))
        except ValueError:
            raise ValueError(f"Niepoprawny punkt '{token}'. Podaj czas:Mb/s, np. 20:1.2.") from None
    validate_profile(points)
    return points


def parse_fixed_rate(value):
    error = "Wybierz stały wariant filmu: 0.5, 1, 2 lub 4 Mb/s."
    try:
        rate = float(str(value).replace(",", "."))
    except ValueError:
        raise ValueError(error) from None
    if rate not in RATES:
        raise ValueError(error)
    return rate


def profile_names():
    saved = sorted(normalize("NFC", p.stem) for p in PROFILE_DIR.glob("*.txt") if p.is_file())
    return list(dict.fromkeys([*PROFILES, *saved]))


def add_profile(name, tokens, fixed_rate=DEFAULT_FIXED_RATE):
    name = profile_name(name)
    points = parse_points(tokens)
    rate = parse_fixed_rate(fixed_rate)
    path = PROFILE_DIR / f"{name}.txt"
    if name in PROFILES:
        raise ValueError(f"'{name}' to profil wbudowany. Wybierz inną nazwę.")
    PROFILE_DIR.mkdir(exist_ok=True)
    # Udostępnij dopiero kompletny plik. Równoczesny zapis tej samej nazwy jej nie nadpisze.
    with TemporaryDirectory(dir=PROFILE_DIR) as tmp:
        ready = Path(tmp) / "profil.txt"
        content = f"stale={rate:g}\n" + "".join(f"{t}:{c}\n" for t, c in points)
        ready.write_text(content, encoding="utf-8")
        try:
            path.hardlink_to(ready)
        except FileExistsError:
            raise ValueError(f"Profil '{name}' już istnieje. Wybierz inną nazwę.") from None
    return path


def load_profile(name):
    name = profile_name(name)
    if name in PROFILES:
        return Profile(PROFILES[name])
    path = PROFILE_DIR / f"{name}.txt"
    try:
        tokens = path.read_text(encoding="utf-8").split()
        rate = DEFAULT_FIXED_RATE
        if tokens and tokens[0].startswith("stale="):
            rate = parse_fixed_rate(tokens.pop(0).split("=", 1)[1])
        return Profile(parse_points(tokens), rate)
    except FileNotFoundError:
        raise ValueError(f"Nie znaleziono profilu '{name}'. Zobacz: python main.py profile") from None
    except ValueError as error:
        raise ValueError(f"Błąd w pliku {path.name}: {error}") from error
