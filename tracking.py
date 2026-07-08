from datetime import datetime

import yfinance as yf

from config import (
    TARGET_PCT,
    STOP_LOSS_PCT,
    MAX_HOLD_DAYS
)

from database import (
    get_open_signals,
    close_signal
)


def get_current_price(ticker: str):

    try:

        stock = yf.Ticker(ticker)

        fast = stock.fast_info

        price = (
            fast.get("lastPrice")
            or fast.get("regularMarketPrice")
            or fast.get("previousClose")
        )

        if price is None:
            return None

        return float(price)

    except Exception as e:

        print(f"[Yahoo] {ticker}: {e}")

        return None


def check_signals():

    open_signals = get_open_signals()

    if not open_signals:

        print("📭 Ochiq signal yo'q.")

        return []

    closed_today = []

    for signal in open_signals:

        ticker = signal["ticker"]

        current_price = get_current_price(ticker)

        if current_price is None:

            continue

        entry_price = signal["entry_price"]

        pct = (
            (current_price - entry_price)
            / entry_price
        ) * 100

        days = (
            datetime.now()
            - datetime.fromisoformat(signal["entry_datetime"])
        ).days

        if pct >= TARGET_PCT:

            close_signal(
                signal,
                current_price,
                pct,
                "profit"
            )

            closed_today.append(signal)

            continue

        if pct <= STOP_LOSS_PCT:

            close_signal(
                signal,
                current_price,
                pct,
                "loss"
            )

            closed_today.append(signal)

            continue

        if days >= MAX_HOLD_DAYS:

            close_signal(
                signal,
                current_price,
                pct,
                "expired"
            )

            closed_today.append(signal)

            continue

        print(
            f"{ticker:6} | "
            f"{pct:+6.2f}% | "
            f"${entry_price:.2f} → ${current_price:.2f}"
        )

    return closed_today
