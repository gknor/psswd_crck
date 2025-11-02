#!/usr/bin/env python3
import sys
import time
import string
import math
from itertools import product

ON_WINDOWS = sys.platform.startswith("win")
if ON_WINDOWS:
    import msvcrt  # kbhit(), getwch() dla nieblokującego przerwania

def choose_charset():
    options = {
        "1": ("cyfry (0-9)", string.digits),
        "2": ("małe litery (a-z)", string.ascii_lowercase),
        "3": ("duże litery (A-Z)", string.ascii_uppercase),
        "4": ("litery (a-zA-Z)", string.ascii_letters),
        "5": ("litery+cyfry (a-zA-Z0-9)", string.ascii_letters + string.digits),
        "6": ("litery+cyfry+znaki (drukowalne)", string.ascii_letters + string.digits + string.punctuation),
        "7": ("własny zestaw", None),
    }
    print("Wybierz alfabet znaków:")
    for k, (name, _) in options.items():
        print(f"  {k}. {name}")
    while True:
        choice = input("Twój wybór [1-7]: ").strip()
        if choice in options:
            name, charset = options[choice]
            if choice == "7":
                custom = input("Podaj własny zestaw znaków: ")
                if not custom:
                    print("Pusty alfabet jest niedozwolony, spróbuj ponownie.")
                    continue
                return "własny", custom
            return name, charset
        print("Nieprawidłowy wybór, spróbuj ponownie.")

def user_stop_requested() -> bool:
    if not ON_WINDOWS:
        return False
    if msvcrt.kbhit():
        ch = msvcrt.getwch()
        if ch.lower() == "s":
            return True
    return False

def format_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds*1000:.1f} ms"
    units = [
        ("lat", 365.25*24*3600),
        ("dni", 24*3600),
        ("h", 3600),
        ("min", 60),
        ("s", 1),
    ]
    parts = []
    rem = seconds
    for name, unit in units:
        if rem >= unit:
            val = int(rem // unit)
            rem -= val * unit
            parts.append(f"{val} {name}")
        if len(parts) >= 2 and name in ("min","s"):
            break
    if not parts:
        parts.append(f"{seconds:.2f} s")
    return " ".join(parts)

def benchmark_rate(charset: str, n: int, target_seconds: float = 0.25, max_attempts: int = 500_000) -> float:
    if n == 0:
        return 10_000_000.0  # trywialny przypadek: 0-długość
    attempts = 0
    start = time.perf_counter()
    for tup in product(charset, repeat=n):
        _ = ''.join(tup)
        attempts += 1
        if attempts >= max_attempts:
            break
        if (attempts & 0x3FFF) == 0:  # co ~16k kroków
            if time.perf_counter() - start >= target_seconds:
                break
    elapsed = time.perf_counter() - start
    return attempts / elapsed if elapsed > 0 else 0.0

def estimate_times(k: int, n: int, rate: float):
    total = k ** n
    best = 1 / rate if rate > 0 else math.inf
    avg = (total / 2) / rate if rate > 0 else math.inf
    worst = total / rate if rate > 0 else math.inf
    return total, best, avg, worst

def brute_force(secret: str, charset: str, update_every: int = 50_000):
    n = len(secret)
    if n == 0:
        return "", 0, 0.0, False, False
    if not set(secret).issubset(set(charset)):
        return None, 0, 0.0, True, False

    attempts = 0
    start = time.perf_counter()
    try:
        for tup in product(charset, repeat=n):
            guess = ''.join(tup)
            attempts += 1

            if attempts % update_every == 0:
                elapsed = time.perf_counter() - start
                rate = attempts / elapsed if elapsed > 0 else 0.0
                print(f"\rPróby: {attempts:,} | Ostatnia: {guess} | Czas: {elapsed:.3f}s | ~{rate:,.0f} prób/s", end="", flush=True)
                if user_stop_requested():
                    print()
                    return None, attempts, elapsed, False, True

            if guess == secret:
                elapsed = time.perf_counter() - start
                if attempts % update_every != 0:
                    print()
                return guess, attempts, elapsed, False, False

    except KeyboardInterrupt:
        elapsed = time.perf_counter() - start
        if attempts % update_every != 0:
            print()
        print(f"\nPrzerwano (Ctrl+C) po {attempts:,} próbach i {elapsed:.3f}s.")
        return None, attempts, elapsed, False, True

    elapsed = time.perf_counter() - start
    if attempts % update_every != 0:
        print()
    return None, attempts, elapsed, False, False

def main_once():
    name, charset = choose_charset()
    secret = input("Wpisz hasło do symulacji: ")
    n = len(secret)
    k = len(charset)
    print(f"Długość hasła: {n} | Alfabet: {name} (|Σ|={k})")

    # Szybki benchmark tempa prób/s dla zadanej długości
    rate = benchmark_rate(charset, n, target_seconds=0.3)
    total, best, avg, worst = estimate_times(k, n, rate)

    print(f"Szacowana przestrzeń: {total:,} kombinacji | Zmierzone tempo: ~{rate:,.0f} prób/s")
    print(f"Szacowany czas: najlepszy ~{format_duration(best)}, średni ~{format_duration(avg)}, najgorszy ~{format_duration(worst)}")
    if ON_WINDOWS:
        print("Start odgadywania… (Ctrl+C lub klawisz 's' aby przerwać)")
    else:
        print("Start odgadywania… (Ctrl+C aby przerwać)")

    guess, attempts, elapsed, out_of_charset, aborted = brute_force(secret, charset)

    if out_of_charset:
        print("Hasło zawiera znak spoza wybranego alfabetu — to przeszukiwanie nie może się powieść.")
        return

    if aborted:
        return

    if guess is None:
        print("Nie znaleziono hasła w wybranym alfabecie.")
        return

    print(f"Znaleziono hasło: {guess}")
    print(f"Czas: {elapsed:.3f}s | Próby: {attempts:,}")

def main():
    print("=== Symulator łamania hasła (konsola) ===")
    while True:
        try:
            main_once()
        except KeyboardInterrupt:
            print("\nPrzerwano w menu — wracam do początku.")
        choice = input("Uruchomić ponownie? [T/n]: ").strip().lower()
        if choice == "n":
            break

if __name__ == "__main__":
    main()
