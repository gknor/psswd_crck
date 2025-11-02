# password_cracker_nicegui_autodetect_reveal_fixed.py
import asyncio
import time
import string
import math
from itertools import product
from nicegui import ui

# Predefiniowane alfabety
CHARSETS = {
    "cyfry (0-9)": string.digits,
    "małe litery (a-z)": string.ascii_lowercase,
    "duże litery (A-Z)": string.ascii_uppercase,
    "litery (a-zA-Z)": string.ascii_letters,
    "litery+cyfry (a-zA-Z0-9)": string.ascii_letters + string.digits,
    "drukowalne (a-zA-Z0-9 + !@#… + spacja)": string.ascii_letters + string.digits + string.punctuation + " ",
}

DETECT_AUTO = "wykryj (auto)"
DETECTED_FROM_PWD = "znaki z hasła (auto)"

# Uchwyt na bieżące zadanie brute force i zadanie krótkiego odsłaniania hasła
task: asyncio.Task | None = None
reveal_task: asyncio.Task | None = None

def format_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds*1000:.1f} ms"
    units = [("lat", 365.25*24*3600), ("dni", 24*3600), ("h", 3600), ("min", 60), ("s", 1)]
    parts, rem = [], seconds
    for name, unit in units:
        if rem >= unit:
            val = int(rem // unit)
            rem -= val * unit
            parts.append(f"{val} {name}")
        if len(parts) >= 2 and name in ("min", "s"):
            break
    return " ".join(parts) if parts else f"{seconds:.2f} s"

def detect_charset_label_and_value(secret: str) -> tuple[str, str]:
    S = set(secret)
    order = [
        "cyfry (0-9)",
        "małe litery (a-z)",
        "duże litery (A-Z)",
        "litery (a-zA-Z)",
        "litery+cyfry (a-zA-Z0-9)",
        "drukowalne (a-zA-Z0-9 + !@#… + spacja)",
    ]
    for label in order:
        if S.issubset(set(CHARSETS[label])):
            return label, CHARSETS[label]
    return DETECTED_FROM_PWD, "".join(sorted(S))

def benchmark_rate(charset: str, n: int, target_seconds: float = 0.25, max_attempts: int = 300_000) -> float:
    if n == 0:
        return 10_000_000.0
    attempts = 0
    start = time.perf_counter()
    for tup in product(charset, repeat=n):
        _ = ''.join(tup)
        attempts += 1
        if attempts >= max_attempts:
            break
        if (attempts & 0x3FFF) == 0 and (time.perf_counter() - start) >= target_seconds:
            break
    elapsed = time.perf_counter() - start
    return attempts / elapsed if elapsed > 0 else 0.0

async def crack(secret: str, charset: str, status_lbl, result_lbl, result_big_lbl, prog, update_every: int = 20_000):
    n = len(secret)
    k = len(charset)
    total = k ** n if n > 0 else 1
    attempts = 0
    start = time.perf_counter()
    try:
        for tup in product(charset, repeat=n):
            guess = ''.join(tup)
            attempts += 1

            if attempts % update_every == 0 or attempts == 1:
                elapsed = time.perf_counter() - start
                rate = attempts / elapsed if elapsed > 0 else 0.0
                frac = min(1.0, attempts / total) if total else 1.0
                prog.value = frac
                status_lbl.text = f"Próby: {attempts:,} | Ostatnia: {guess} | Czas: {elapsed:.3f}s | ~{rate:,.0f} prób/s"
                await asyncio.sleep(0)

            if guess == secret:
                elapsed = time.perf_counter() - start
                prog.value = 1.0
                result_lbl.text = f"Znaleziono hasło: {guess} | Czas: {elapsed:.3f}s | Próby: {attempts:,}"
                result_big_lbl.text = f"🎉 {guess} 🎉"
                result_big_lbl.style(
                    "font-size: 72px; font-weight: 800; "
                    "background: linear-gradient(90deg,#10b981,#06b6d4,#8b5cf6); "
                    "-webkit-background-clip: text; background-clip: text; color: transparent; "
                    "text-shadow: 0 2px 12px rgba(0,0,0,0.15);"
                )
                ui.notify(f"Znaleziono w {elapsed:.3f}s po {attempts:,} próbach!", type='positive', position='top', timeout=4000)
                return
        result_lbl.text = "Nie znaleziono hasła w wybranym alfabecie."
    except asyncio.CancelledError:
        elapsed = time.perf_counter() - start
        result_lbl.text = f"Przerwano po {attempts:,} próbach i {elapsed:.3f}s."
        result_big_lbl.text = ""
        raise

with ui.column().classes('items-center gap-4 w-full'):
    ui.label('Symulator łamania hasła (NiceGUI)').classes('text-3xl font-semibold')

with ui.card().classes('w-full max-w-3xl'):
    # Dodajemy także "znaki z hasła (auto)" do listy, by było widać wynik auto-detekcji
    options = [DETECT_AUTO] + list(CHARSETS.keys()) + [DETECTED_FROM_PWD]
    with ui.row().classes('w-full items-end gap-3'):
        charset_select = ui.select(options=options, value=DETECT_AUTO, label='Alfabet')
        # Pole hasła z ikoną "oka"; będzie też krótkie odsłanianie po każdej zmianie
        pwd = ui.input('Hasło', password=True, password_toggle_button=True).classes('w-full')

    est_lbl = ui.label('Estymacja pojawi się po wciśnięciu Start')
    prog = ui.linear_progress(value=0.0).props('instant-feedback')
    status_lbl = ui.label('')
    result_lbl = ui.label('')
    result_big_lbl = ui.label('').classes('self-center')

    async def flash_reveal(delay: float = 0.9):
        # Krótkie odsłonięcie hasła po wpisaniu znaku
        pwd.props('type=text')
        try:
            await asyncio.sleep(delay)
        finally:
            # Zawsze wróć do maskowania
            pwd.props('type=password')

    def on_pwd_change():
        global reveal_task
        secret = pwd.value or ""

        # Auto-wykrycie alfabetu przy wpisywaniu
        if secret:
            detected_label, _ = detect_charset_label_and_value(secret)
            charset_select.value = detected_label if detected_label in CHARSETS else DETECTED_FROM_PWD

        # Restart krótkiego odsłonięcia
        if reveal_task and not reveal_task.done():
            reveal_task.cancel()
        reveal_task = asyncio.create_task(flash_reveal(0.9))

    pwd.on_value_change(lambda _: on_pwd_change())

    async def on_start():
        global task
        if task and not task.done():
            ui.notify('Zadanie już trwa — najpierw naciśnij Stop.', type='warning')
            return

        secret = pwd.value or ""
        sel = charset_select.value

        # Obsługa trybu auto
        if sel == DETECT_AUTO:
            detected_label, detected_charset = detect_charset_label_and_value(secret)
            if detected_label in CHARSETS:
                sel = detected_label
                charset_select.value = detected_label
                charset = CHARSETS[detected_label]
            else:
                sel = DETECTED_FROM_PWD
                charset_select.value = DETECTED_FROM_PWD
                charset = detected_charset
        else:
            if sel in CHARSETS:
                charset = CHARSETS[sel]
            elif sel == DETECTED_FROM_PWD:
                _, charset = detect_charset_label_and_value(secret)
            else:
                charset = CHARSETS["drukowalne (a-zA-Z0-9 + !@#… + spacja)"]

        n, k = len(secret), len(charset)

        if n == 0:
            ui.notify("Hasło jest puste.", type='warning')
            return
        if not set(secret).issubset(set(charset)):
            result_lbl.text = "Hasło zawiera znak spoza wybranego alfabetu — to przeszukiwanie nie może się powieść."
            result_big_lbl.text = ""
            return

        # Szybki benchmark tempa i estymacja
        r = benchmark_rate(charset, n, target_seconds=0.3)
        total = (k ** n) if n > 0 else 1
        best = 1 / r if r > 0 else math.inf
        avg = (total / 2) / r if r > 0 else math.inf
        worst = total / r if r > 0 else math.inf
        est_lbl.text = (
            f"Przestrzeń: {total:,} | Tempo: ~{r:,.0f} prób/s | "
            f"Najlepszy ~{format_duration(best)}, średni ~{format_duration(avg)}, najgorszy ~{format_duration(worst)}"
        )

        # Reset i start
        prog.value = 0.0
        status_lbl.text = "Start łamania…"
        result_lbl.text = ""
        result_big_lbl.text = ""
        task = asyncio.create_task(crack(secret, charset, status_lbl, result_lbl, result_big_lbl, prog))

    def on_stop():
        global task
        if task and not task.done():
            task.cancel()

    with ui.row().classes('gap-4'):
        ui.button('Start', on_click=on_start, color='green')
        ui.button('Stop', on_click=on_stop, color='red')

ui.run(port=8080)
