"""Zapis i odczyt profili użytkownika. Każdy wiersz pliku to czas:Mb/s."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unicodedata import normalize

from simulation import PROFILES, validate_profile

PROFILE_DIR = Path(__file__).resolve().parent / "profile"


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


def profile_names():
    saved = sorted(normalize("NFC", p.stem) for p in PROFILE_DIR.glob("*.txt") if p.is_file())
    return list(dict.fromkeys([*PROFILES, *saved]))


def add_profile(name, tokens):
    name = profile_name(name)
    points = parse_points(tokens)
    path = PROFILE_DIR / f"{name}.txt"
    if name in PROFILES:
        raise ValueError(f"'{name}' to profil wbudowany. Wybierz inną nazwę.")
    PROFILE_DIR.mkdir(exist_ok=True)
    # Udostępnij dopiero kompletny plik. Równoczesny zapis tej samej nazwy jej nie nadpisze.
    with TemporaryDirectory(dir=PROFILE_DIR) as tmp:
        ready = Path(tmp) / "profil.txt"
        ready.write_text("".join(f"{t}:{c}\n" for t, c in points), encoding="utf-8")
        try:
            path.hardlink_to(ready)
        except FileExistsError:
            raise ValueError(f"Profil '{name}' już istnieje. Wybierz inną nazwę.") from None
    return path


def load_profile(name):
    name = profile_name(name)
    if name in PROFILES:
        return PROFILES[name]
    path = PROFILE_DIR / f"{name}.txt"
    try:
        return parse_points(path.read_text(encoding="utf-8").split())
    except FileNotFoundError:
        raise ValueError(f"Nie znaleziono profilu '{name}'. Zobacz: python main.py profile") from None
    except ValueError as error:
        raise ValueError(f"Błąd w pliku {path.name}: {error}") from error
