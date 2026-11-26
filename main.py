"""Demo i odtwarzalna analiza projektu. Uruchom: python main.py."""

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # PNG, także na komputerze bez środowiska graficznego
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
import numpy as np

import fis
from profiles import add_profile, load_profile, parse_fixed_rate, profile_name, profile_names
from simulation import DEFAULT_FIXED_RATE, PROFILES, SEGMENT_SECONDS, metrics, policies, simulate

OUT = Path(__file__).resolve().parent / "wyniki"
COLORS = ("#315481", "#0d8176", "#b34e26", "#714c86")


def save(fig, name):
    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / name, dpi=160, facecolor="white")
    plt.close(fig)


def example(speed, buffer):
    result = fis.infer(speed, buffer)
    print(f"Pomiar {speed:g} Mb/s   |   Bufor {buffer:g} s")
    for row, column in zip(*np.nonzero(result.strengths)):
        print(f"  bufor {fis.BUFFER_LABELS[row]}, przepustowość {fis.SPEED_LABELS[column]}"
              f" → {fis.RULES[row, column]:g} Mb/s   siła {result.strengths[row, column]:.3f}")
    print(f"Centroid {result.target:.3f} Mb/s   →   wybrany segment {result.rate:g} Mb/s")


def model_plots():
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.4), layout="constrained")
    inputs = (
        (axes[0], fis.SPEED_MAX, fis.SPEED_ANCHORS, fis.SPEED_LABELS, "Przepustowość [Mb/s]"),
        (axes[1], fis.BUFFER_MAX, fis.BUFFER_ANCHORS, fis.BUFFER_LABELS, "Bufor [s]"),
    )
    for ax, limit, anchors, labels, title in inputs:
        x = np.linspace(0, limit, 201)
        for curve, label, color in zip(fis.memberships(x, anchors), labels, COLORS):
            ax.plot(x, curve, label=label, color=color)
        ax.set_xlabel(title)
    for curve, label, color in zip(fis.OUTPUT_SETS, fis.RATE_LABELS, COLORS):
        axes[2].plot(fis.OUTPUT_AXIS, curve, label=label, color=color)
    axes[2].set_xlabel("Rekomendacja [Mb/s]")
    axes[0].set_ylabel("Stopień przynależności")
    for ax in axes:
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.27), ncol=2, fontsize=9)
        ax.grid(alpha=0.2)
    save(fig, "zbiory.png")

    result = fis.infer(4, 10)
    fig, ax = plt.subplots(figsize=(8, 3.1), layout="constrained")
    ax.fill_between(fis.OUTPUT_AXIS, result.aggregate, color=COLORS[1], alpha=0.7)
    ax.axvline(result.target, color=COLORS[2], linestyle="--", label=f"Centroid {result.target:g} Mb/s")
    ax.set(xlabel="Rekomendacja [Mb/s]", ylabel="Przynależność po agregacji",
           title="Cztery aktywne reguły przy 4 Mb/s i 10 s bufora")
    ax.legend()
    save(fig, "agregacja.png")

    speeds = np.linspace(0, fis.SPEED_MAX, 81)
    buffers = np.linspace(0, fis.BUFFER_MAX, 81)
    targets = np.empty((len(buffers), len(speeds)))
    chosen = np.empty_like(targets)
    for i, buffer in enumerate(buffers):
        for j, speed in enumerate(speeds):
            decision = fis.infer(speed, buffer)
            targets[i, j], chosen[i, j] = decision.target, decision.rate

    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained", sharey=True)
    continuous = axes[0].pcolormesh(speeds, buffers, targets, shading="nearest", cmap="viridis")
    fig.colorbar(continuous, ax=axes[0], label="Mb/s")
    cmap = ListedColormap(("#462c70", "#35678c", "#249488", "#e5c95b"))
    discrete = axes[1].pcolormesh(speeds, buffers, chosen, shading="nearest",
                                   cmap=cmap, norm=BoundaryNorm((0, .75, 1.5, 3, 5), 4))
    fig.colorbar(discrete, ax=axes[1], label="Mb/s", ticks=fis.RATES)
    axes[0].set_title("Rekomendacja FIS")
    axes[1].set_title("Wybrany wariant segmentu")
    axes[0].set_ylabel("Zapas odtwarzania [s]")
    for ax in axes:
        ax.set(xlabel="Ostatni pomiar łącza [Mb/s]", xlim=(0, fis.SPEED_MAX), ylim=(0, fis.BUFFER_MAX))
    save(fig, "mapa.png")


def buffer_path(log):
    times, levels = [], []
    for segment in log:
        before_delivery = max(0.0, segment.buffer_after - SEGMENT_SECONDS)
        times.extend([segment.start, segment.end - segment.stall, segment.end, segment.end])
        levels.extend([segment.buffer_before, before_delivery, before_delivery, segment.buffer_after])
    return times + [log[-1].end + log[-1].buffer_after], levels + [0.0]


def plot_throughput(ax, profile, log, finish):
    points = [(t, c) for t, c in profile if t < finish]
    points.append((finish, points[-1][1]))
    times, speeds = zip(*points)
    ax.step(times, speeds, where="post", color=COLORS[0], label="Rzeczywiste łącze")
    ax.scatter([s.start for s in log[1:]], [s.estimated_speed for s in log[1:]],
               s=10, color=COLORS[2], label="Ostatni pomiar FIS")
    ax.legend(loc="lower right", fontsize=8, ncol=2)
    ax.set_ylabel("Łącze [Mb/s]")


def plot_buffers(ax, log, fixed, fixed_label):
    for s in fixed:
        if s.stall > 1e-9:
            ax.axvspan(s.end - s.stall, s.end, color="#e57865", alpha=.3)
    ax.plot(*buffer_path(fixed), color=COLORS[2], alpha=.8, linestyle="--", label=f"{fixed_label} Mb/s")
    ax.plot(*buffer_path(log), color=COLORS[1], label="FIS")
    ax.legend(loc="upper right", ncol=2, fontsize=8)
    ax.set_ylabel("Bufor [s]")


def plot_fis_rate(ax, log):
    ax.step([s.start for s in log] + [log[-1].end], [s.rate for s in log] + [log[-1].rate],
            where="post", color=COLORS[0])
    ax.set(yticks=fis.RATES, ylabel="Wariant FIS\n[Mb/s]", xlabel="Czas od pierwszego żądania [s]")


def trace_plot(name, profile, log, fixed, fixed_label):
    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(10, 5.6), layout="constrained")
    finish = max(run[-1].end + run[-1].buffer_after for run in (log, fixed))
    plot_throughput(axes[0], profile, log, finish)
    plot_buffers(axes[1], log, fixed, fixed_label)
    plot_fis_rate(axes[2], log)
    axes[0].set_title(f"Profil {name}  |  czerwone pola oznaczają przerwy strategii stałej")
    for ax in axes:
        ax.grid(alpha=.2)
        ax.set_xlim(0, finish)
    save(fig, f"przebieg_{name}.png")


def all_fixed_plot(name, profile, logs):
    fig = plt.figure(figsize=(12, 8), layout="constrained")
    grid = fig.add_gridspec(4, 2, height_ratios=(1, 1.5, 1.5, 1))
    log = logs["FIS"]
    finish = max(run[-1].end + run[-1].buffer_after for run in logs.values())
    fis_stall = f"{metrics(log)['zatrzymania_s']:.2f}".replace(".", ",")
    fig.suptitle(f"Profil {name} · FIS i cztery stałe warianty filmu\n"
                 f"Przerwy FIS {fis_stall} s · czerwone pola oznaczają przerwy wariantu stałego")

    network = fig.add_subplot(grid[0, :])
    plot_throughput(network, profile, log, finish)
    fixed_runs = [(label, run) for label, run in logs.items() if label != "FIS"]
    for i, (label, fixed) in enumerate(fixed_runs):
        ax = fig.add_subplot(grid[1 + i // 2, i % 2], sharex=network)
        title = label.replace(".", ",")
        stall = f"{metrics(fixed)['zatrzymania_s']:.2f}".replace(".", ",")
        plot_buffers(ax, log, fixed, title)
        ax.set(title=f"FIS / {title} Mb/s · przerwy wariantu stałego {stall} s",
               ylim=(0, fis.BUFFER_MAX + SEGMENT_SECONDS))

    rate_ax = fig.add_subplot(grid[3, :], sharex=network)
    plot_fis_rate(rate_ax, log)
    network.set_xlim(0, finish)
    for ax in fig.axes:
        ax.grid(alpha=.2)
    save(fig, f"porownanie_{name}.png")


def compare(profiles, fixed_rate=None, *, all_fixed=False):
    rows = []
    width = max(10, max(map(len, profiles)))
    print(f"\n{'Profil':{width}} {'Strategia':10} Start [s]  Zatrzymania [s]  Średnia [Mb/s]  Zmiany")
    for name, profile in profiles.items():
        rate = profile.fixed_rate if fixed_rate is None else fixed_rate
        logs = {label: simulate(profile.points, policy)
                for label, policy in policies(rate, all_fixed=all_fixed).items()}
        for policy_name, log in logs.items():
            m = metrics(log)
            print(f"{name:{width}} {policy_name:10} {m['start_s']:9.2f} {m['zatrzymania_s']:16.2f}"
                  f" {m['srednia_Mb_s']:15.2f} {m['zmiany']:7}")
            rows.append({"profil": name, "strategia": policy_name, **m})
        if all_fixed:
            all_fixed_plot(name, profile.points, logs)
        else:
            fixed_label = f"Stałe {rate:g}"
            trace_plot(name, profile.points, logs["FIS"], logs[fixed_label], fixed_label)
    return rows


def main():
    parser = argparse.ArgumentParser(description="Dobór przepływności segmentu wideo")
    sub = parser.add_subparsers(dest="command")
    demo = sub.add_parser("demo", help="Jedna decyzja i porównanie FIS ze stałą jakością")
    demo.add_argument("profil", nargs="?", default="spadek", help="Nazwa z polecenia 'profile'")
    demo_options = demo.add_mutually_exclusive_group()
    demo_options.add_argument("--stale", metavar="MB/S",
                              help="Stały wariant filmu dla tego uruchomienia (0.5, 1, 2 lub 4)")
    demo_options.add_argument("--wszystkie", action="store_true",
                              help="Pokaż FIS i wszystkie cztery stałe warianty na jednym PNG")
    sub.add_parser("profile", help="Pokaż nazwy profili wbudowanych i zapisanych")
    add = sub.add_parser("dodaj-profil", help="Zapisz własny profil łącza",
                         epilog="Przykład: python main.py dodaj-profil moj 0:5 20:1.2 55:4")
    add.add_argument("nazwa")
    add.add_argument("punkty", nargs="+", metavar="CZAS:MB/S", help="Czas od początku [s] i przepustowość [Mb/s]")
    add.add_argument("--stale", metavar="MB/S", default=DEFAULT_FIXED_RATE,
                     help="Zapisz stały wariant filmu (0.5, 1, 2 lub 4, domyślnie 2)")
    case = sub.add_parser("decyzja", help="Prześledź reguły dla dwóch liczb")
    case.add_argument("pomiar", type=float)
    case.add_argument("bufor", type=float)
    sub.add_parser("analiza", help="Odtwórz wszystkie wykresy i tabelę CSV")
    args = parser.parse_args()
    try:
        run(args)
    except (ValueError, OSError) as error:
        parser.error(str(error))


def run(args):
    if args.command == "profile":
        for name in profile_names():
            print(f"{name} ({'wbudowany' if name in PROFILES else 'własny'})")
    elif args.command == "dodaj-profil":
        path = add_profile(args.nazwa, args.punkty, args.stale)
        print(f"Zapisano: {path}\nUruchom: python main.py demo {path.stem}")
    elif args.command == "decyzja":
        example(args.pomiar, args.bufor)
    elif args.command == "analiza":
        profiles = {name: load_profile(name) for name in profile_names()}
        model_plots()
        rows = compare(profiles)
        with (OUT / "porownanie.csv").open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        print(f"Pełna analiza: {OUT}")
    else:
        name = profile_name(getattr(args, "profil", "spadek"))
        profile = load_profile(name)
        option = getattr(args, "stale", None)
        fixed_rate = parse_fixed_rate(option) if option is not None else None
        all_fixed = getattr(args, "wszystkie", False)
        print("Przykład pojedynczej decyzji (te same wejścia dla każdego demo)")
        example(4, 10)
        compare({name: profile}, fixed_rate, all_fixed=all_fixed)
        prefix = "porownanie" if all_fixed else "przebieg"
        print(f"Wykres: {OUT / f'{prefix}_{name}.png'}")


if __name__ == "__main__":
    main()
