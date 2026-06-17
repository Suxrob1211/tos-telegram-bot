"""
TOS Alert → Telegram Bot (v5)
Real-time Finviz screenshot + Yahoo Finance ma'lumotlari
"""

import imaplib
import email
import time
import re
import os
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

GMAIL_USER       = os.getenv("GMAIL_USER")
GMAIL_APP_PASS   = os.getenv("GMAIL_APP_PASSWORD")
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TOS_SENDER       = "alerts@thinkorswim.com"
CHECK_INTERVAL   = 30
MIN_RVOL         = 1.0
RSI_MIN          = 30
RSI_MAX          = 80
SENT_IDS_FILE    = "sent_ids.txt"

def load_sent_ids() -> set:
    if not os.path.exists(SENT_IDS_FILE):
        return set()
    with open(SENT_IDS_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

def save_sent_id(msg_id: str):
    with open(SENT_IDS_FILE, "a") as f:
        f.write(msg_id + "\n")

ALREADY_SENT = load_sent_ids()

# ── Playwright bilan real-time screenshot ────────────────────────────────────
try:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process",
                "--disable-web-security",
            ]
        )

        page = browser.new_page(
            viewport={"width": 1600, "height": 1000},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0 Safari/537.36"
            )
        )

        url = f"https://finviz.com/quote.ashx?t={ticker}&p=d"

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        page.wait_for_timeout(5000)

        screenshot = page.screenshot(
            type="png",
            full_page=False
        )

        browser.close()

        if screenshot and len(screenshot) > 10000:
            print(f"[Screenshot] {ticker} OK")
            return screenshot

except Exception as e:
    print(f"[Screenshot xato] {ticker}: {e}")

return None

def get_chart_image(ticker: str) -> bytes | None:
    """
    1. Playwright screenshot (real-time)
    2. Finviz chart URL (fallback)
    """
    # 1-usul: Playwright screenshot
    img = get_finviz_screenshot(ticker)
    if img:
        return img

    # 2-usul: Finviz chart URL dan yuklab olish
    try:
        url = f"https://charts.finviz.com/chart.ashx?t={ticker}&ty=c&ta=1&p=d&s=l&_={int(time.time())}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://finviz.com/",
            "Accept": "image/png,image/*,*/*",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        if resp.content[:4] == b'\x89PNG':
            print(f"[Chart URL] {ticker} grafigi olindi")
            return resp.content
    except Exception as e:
        print(f"[Chart URL xato] {e}")

    return None

# ── Texnik indikatorlar ───────────────────────────────────────────────────────
def calc_rsi(closes: pd.Series, period: int = 14) -> float:
    try:
        if len(closes) < period + 1:
            return 0.0
        delta = closes.diff().dropna()
        gain  = delta.clip(lower=0).rolling(period).mean()
        loss  = (-delta.clip(upper=0)).rolling(period).mean()
        rs    = gain / loss
        rsi   = 100 - (100 / (1 + rs))
        val   = rsi.dropna().iloc[-1]
        return round(float(val), 1) if not pd.isna(val) else 0.0
    except Exception:
        return 0.0

def calc_macd(closes: pd.Series) -> str:
    try:
        if len(closes) < 26:
            return "N/A"
        ema12  = closes.ewm(span=12, adjust=False).mean()
        ema26  = closes.ewm(span=26, adjust=False).mean()
        macd   = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        return "Bullish ↑" if macd.iloc[-1] > signal.iloc[-1] else "Bearish ↓"
    except Exception:
        return "N/A"

# ── Yahoo Finance ─────────────────────────────────────────────────────────────
def get_stock_info(ticker: str) -> dict:
    try:
        stock = yf.Ticker(ticker)
        info  = stock.info

        price = float(
            info.get("currentPrice") or
            info.get("regularMarketPrice") or
            info.get("navPrice") or 0.0
        )
        prev_close = float(info.get("previousClose") or info.get("regularMarketPreviousClose") or 0.0)
        change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0.0
        volume     = int(info.get("volume") or info.get("regularMarketVolume") or 0)
        avg_vol    = int(info.get("averageVolume") or 0)
        rvol       = round(volume / avg_vol, 2) if avg_vol else 0.0
        market_cap = info.get("marketCap") or 0
        sector     = info.get("sector") or "N/A"
        company    = info.get("longName") or info.get("shortName") or ticker

        hist = stock.history(period="1y")
        if not hist.empty:
            closes     = hist["Close"].dropna()
            rsi        = calc_rsi(closes)
            macd_trend = calc_macd(closes)
            support    = round(float(hist["Low"].min()), 2)
            resistance = round(float(hist["High"].max()), 2)
        else:
            rsi, macd_trend, support, resistance = 0.0, "N/A", 0.0, 0.0

        return {
            "company": company, "sector": sector,
            "price": price, "change_pct": change_pct,
            "volume": volume, "avg_volume": avg_vol, "rvol": rvol,
            "market_cap": market_cap, "rsi": rsi,
            "macd_trend": macd_trend, "support": support, "resistance": resistance,
        }
    except Exception as e:
        print(f"[Yahoo xato] {ticker}: {e}")
        return {}

def format_number(n) -> str:
    n = float(n or 0)
    if n >= 1_000_000_000: return f"{n/1_000_000_000:.2f}B"
    if n >= 1_000_000:     return f"{n/1_000_000:.2f}M"
    if n >= 1_000:         return f"{n/1_000:.2f}K"
    return str(round(n, 2))

# ── Signal filtri ─────────────────────────────────────────────────────────────
def is_strong_signal(d: dict) -> tuple:
    reasons = []
    if d["rvol"] > 0 and d["rvol"] < MIN_RVOL:
        reasons.append(f"RVol past ({d['rvol']} < {MIN_RVOL})")
    if d["rsi"] > 0 and (d["rsi"] < RSI_MIN or d["rsi"] > RSI_MAX):
        reasons.append(f"RSI chegaradan ({d['rsi']})")
    return (False, " | ".join(reasons)) if reasons else (True, "OK")

# ── Xabar yasash ──────────────────────────────────────────────────────────────
def build_message(ticker: str, scanner_name: str) -> tuple:
    d = get_stock_info(ticker)
    if not d or d["price"] == 0:
        return "", False, "Ma'lumot olinmadi"

    passed, reason = is_strong_signal(d)
    if not passed:
        return "", False, reason

    arrow   = "🟢" if d["change_pct"] >= 0 else "🔴"
    rsi     = d["rsi"]
    rsi_label = (f"{rsi} ⚠️ Overbought" if rsi >= 70
                 else f"{rsi} ⚠️ Oversold" if 0 < rsi <= 30
                 else str(rsi) if rsi > 0 else "N/A")

    msg = (
        f"🧠 <b>Algorithm:</b> {scanner_name}\n"
        f"📌 <b>Ticker:</b> <code>{ticker}</code>\n"
        f"🏢 <b>Company:</b> {d['company']}\n"
        f"🏭 <b>Sector:</b> {d['sector']}\n"
        f"💰 <b>Price:</b> ${d['price']:.2f}\n"
        f"📊 <b>% Change:</b> {arrow} {d['change_pct']:+.2f}%\n"
        f"📉 <b>Yesterday Vol:</b> {format_number(d['avg_volume'])}\n"
        f"📈 <b>Current Vol:</b> {format_number(d['volume'])}\n"
        f"⚡ <b>RVol:</b> {d['rvol']}\n"
        f"📊 <b>Market Cap:</b> {format_number(d['market_cap'])}\n"
        f"〰️ <b>RSI (14):</b> {rsi_label}\n"
        f"📉 <b>MACD:</b> {d['macd_trend']}\n"
        f"🎯 <b>Support:</b> ${d['support']} | <b>Resistance:</b> ${d['resistance']}\n"
        f"🕐 <b>Time:</b> {datetime.now().strftime('%H:%M, %d-%b-%Y')}"
    )
    return msg, True, "OK"

# ── Telegram ─────────────────────────────────────────────────────────────────
def send_telegram_photo(caption: str, ticker: str):
    img_bytes = get_chart_image(ticker)

    if img_bytes:
        try:
            url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            resp = requests.post(url,
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "HTML"},
                files={"photo": (f"{ticker}.png", img_bytes, "image/png")},
                timeout=20
            )
            if resp.ok:
                print(f"[Telegram] {ticker} grafik bilan yuborildi ✅")
                return
            print(f"[Telegram photo xato] {resp.text}")
        except Exception as e:
            print(f"[Telegram photo xato] {e}")

    # Grafik chiqmasa — link bilan matn
    caption_with_link = caption + f'\n🔗 <a href="https://finviz.com/quote.ashx?t={ticker}">Finviz grafik</a>'
    send_telegram_text(caption_with_link)

def send_telegram_text(text: str):
    url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML",
    }, timeout=15)
    if not resp.ok:
        print(f"[Telegram matn xato] {resp.text}")

# ── Email parsing ─────────────────────────────────────────────────────────────
def extract_tickers_and_scanner(subject: str, body: str):

    text = subject.strip()

    scanner_name = "TOS Scanner"

    # Alert: New symbol: INSP was added to Trend line .
    # Alert: New symbol: AIT was added to trend + breakout + volume oldin.
    # Alert: New symbols: COP, CVX were added to pullback.

    scanner_match = re.search(
        r"(?:was|were)\s+added\s+to\s+(.+?)(?:\.|$|oldin)",
        text,
        re.IGNORECASE
    )

    if scanner_match:
        scanner_name = scanner_match.group(1).strip()

    tickers = []

    # Single ticker
    m_single = re.search(
        r"New symbol:\s*([A-Z]{1,5})",
        text,
        re.IGNORECASE
    )

    if m_single:
        tickers = [m_single.group(1).upper()]

    # Multiple tickers
    if not tickers:

        m_multi = re.search(
            r"New symbols:\s*(.*?)\s+(?:was|were)\b",
            text,
            re.IGNORECASE
        )

        if m_multi:

            tickers = [
                t.strip().upper()
                for t in m_multi.group(1).split(",")
                if re.match(r"^[A-Z]{1,5}$", t.strip())
            ]

    print(
        f"[Parser] Scanner: '{scanner_name}', "
        f"Tickers: {tickers}"
    )

    return list(dict.fromkeys(tickers)), scanner_name

# ── Email tekshirish ──────────────────────────────────────────────────────────
def check_email():
    mail = None
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_APP_PASS)
        mail.select("inbox")

        since = datetime.now().strftime("%d-%b-%Y")
        _, data = mail.search(None, f'(UNSEEN FROM "{TOS_SENDER}" SINCE "{since}")')
        ids = data[0].split()
        print(f"[Email] {len(ids)} ta yangi TOS alert")

        for eid in ids:
            _, msg_data = mail.fetch(eid, "(RFC822)")
            msg     = email.message_from_bytes(msg_data[0][1])
            subject = msg.get("Subject", "")
            msg_id  = msg.get("Message-ID", str(eid))

            if msg_id in ALREADY_SENT:
                continue

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

            print(f"[Email] Subject: {subject}")

            if not re.search(r"New symbols?\s*:", subject, re.IGNORECASE):
                print("[Skip] Following list email")
                continue

            tickers, scanner_name = extract_tickers_and_scanner(subject, body)

            for ticker in tickers:
                caption, passed, reason = build_message(ticker, scanner_name)
                if not passed:
                    print(f"[Filter] {ticker} o'tmadi: {reason}")
                    continue
                send_telegram_photo(caption, ticker)
                print(f"[Telegram] {ticker} yuborildi ✅")
                time.sleep(2)

            ALREADY_SENT.add(msg_id)
            save_sent_id(msg_id)

    except Exception as e:
        print(f"[Xato] {e}")
    finally:
        try:
            if mail:
                mail.logout()
        except Exception:
            pass

# ── Asosiy tsikl ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 TOS → Telegram bot v5 ishga tushdi!")
    print(f"   Gmail: {GMAIL_USER}")
    print(f"   Kanal: {TELEGRAM_CHAT_ID}")
    print(f"   Har {CHECK_INTERVAL}s tekshiradi...")
    print(f"   Filter: RVol>={MIN_RVOL}, RSI {RSI_MIN}-{RSI_MAX}\n")

    while True:
        check_email()
        time.sleep(CHECK_INTERVAL)
