import re


def parse_signal_message(text: str):
    """
    Telegram kanalidan kelgan signalni parse qiladi.

    Qaytaradi:
    {
        "ticker": "...",
        "scanner": "...",
        "price": ...
    }

    yoki None
    """

    if not text:
        return None

    if "Ticker:" not in text:
        return None

    ticker_match = re.search(
        r"Ticker:\s*(?:<code>)?([A-Z]{1,6})(?:</code>)?",
        text
    )

    price_match = re.search(
        r"Price:\s*\$?([\d,]+(?:\.\d+)?)",
        text
    )

    scanner_match = re.search(
        r"Algorithm:\s*(.+)",
        text
    )

    if not ticker_match:
        return None

    if not price_match:
        return None

    ticker = ticker_match.group(1).strip()

    price = float(
        price_match.group(1).replace(",", "")
    )

    scanner = (
        scanner_match.group(1).strip()
        if scanner_match
        else "Unknown"
    )

    return {
        "ticker": ticker,
        "price": price,
        "scanner": scanner
    }
