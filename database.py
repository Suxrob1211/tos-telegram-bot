import json
import os
from datetime import datetime

from config import SIGNALS_DB


def load_signals():
    """signals_db.json faylidan barcha signallarni o'qiydi."""
    if not os.path.exists(SIGNALS_DB):
        return []

    try:
        with open(SIGNALS_DB, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Database] O'qishda xato: {e}")
        return []


def save_signals(signals):
    """Barcha signallarni JSON faylga yozadi."""
    try:
        with open(SIGNALS_DB, "w", encoding="utf-8") as f:
            json.dump(signals, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[Database] Yozishda xato: {e}")


def signal_exists_today(ticker):
    """Bugungi ochiq signal mavjudligini tekshiradi."""
    today = datetime.now().strftime("%Y-%m-%d")

    signals = load_signals()

    for signal in signals:
        if (
            signal["ticker"] == ticker
            and signal["entry_date"] == today
            and signal["status"] == "open"
        ):
            return True

    return False


def add_signal(ticker, scanner, entry_price):
    """Yangi signal qo'shadi."""

    if signal_exists_today(ticker):
        print(f"[Database] {ticker} bugun allaqachon mavjud.")
        return False

    signals = load_signals()

    signals.append({
        "ticker": ticker,
        "scanner": scanner,
        "entry_price": round(float(entry_price), 2),

        "entry_date": datetime.now().strftime("%Y-%m-%d"),
        "entry_datetime": datetime.now().isoformat(),

        "status": "open",

        "exit_price": None,
        "exit_date": None,
        "pct_change": None,
    })

    save_signals(signals)

    print(f"[Database] {ticker} qo'shildi.")

    return True


def get_open_signals():
    """Faqat ochiq signallarni qaytaradi."""

    signals = load_signals()

    return [
        signal
        for signal in signals
        if signal["status"] == "open"
    ]


def update_signal(updated_signal):
    """Signalni yangilaydi."""

    signals = load_signals()

    for i, signal in enumerate(signals):
        if (
            signal["ticker"] == updated_signal["ticker"]
            and signal["entry_datetime"] == updated_signal["entry_datetime"]
        ):
            signals[i] = updated_signal
            break

    save_signals(signals)


def close_signal(signal, exit_price, pct_change, status):
    """Signalni yopadi."""

    signal["status"] = status
    signal["exit_price"] = round(float(exit_price), 2)
    signal["exit_date"] = datetime.now().strftime("%Y-%m-%d")
    signal["pct_change"] = round(float(pct_change), 2)

    update_signal(signal)

    print(
        f"[Database] {signal['ticker']} yopildi "
        f"({status}) {pct_change:+.2f}%"
    )


def get_all_signals():
    """Barcha signallarni qaytaradi."""
    return load_signals()
