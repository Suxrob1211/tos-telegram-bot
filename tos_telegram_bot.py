"""
TOS Alert → Telegram Bot (v4)
Yahoo Finance dan to'liq ma'lumot + Finviz grafik
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

# ── Sozlamalar ──────────────────────────────────────────────────────────────
GMAIL_USER       = os.getenv("GMAIL_USER")
GMAIL_APP_PASS   = os.getenv("GMAIL_APP_PASSWORD")
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TOS_SENDER       = "alerts@thinkorswim.com"
CHECK_INTERVAL   = 15

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

# ── Yahoo Finance — barcha ma'lumotlar ──────────────────────────────────────
def get_stock_info(ticker: str) -> dict:
    """Yahoo Finance dan to'liq ma'lumot oladi."""
    try:
        stock = yf.Ticker(ticker)
        info  = stock.info

        # Narx
        price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("navPrice")
            or 0.0
        )
        price = float(price) if price else 0.0

        # Oldingi yopilish
        prev_close = float(
            info.get("previousClose")
            or info.get("regularMarketPreviousClose")
            or 0.0
        )
        change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0.0

        # Hajm
        volume  = int(info.get("volume") or info.get("regularMarketVolume") or 0)
        avg_vol = int(info.get("averageVolume") or 0)
        rvol    = round(volume / avg_vol, 2) if avg_vol else 0.0

        # Boshqa ma'lumotlar
        market_cap = info.get("marketCap") or 0
        sector     = info.get("sector") or "N/A"
        company    = info.get("longName") or info.get("shortName") or ticker

        # Tarixiy ma'lumot (RSI, MACD, S/R)
        hist = stock.history(period="1y")
        if not hist.empty:
            closes     = hist["Close"].dropna()
            rsi        = calc_rsi(closes)
            macd_trend = calc_macd(closes)
            support    = round(float(hist["Low"].min()), 2)
            resistance = round(float(hist["High"].max()), 2)
        else:
            rsi        = 0.0
            macd_trend = "N/A"
            support    = 0.0
            resistance = 0.0

        return {
            "company":    company,
            "sector":     sector,
            "price":      price,
            "change_pct": change_pct,
            "volume":     volume,
            "avg_volume": avg_vol,
            "rvol":       rvol,
            "market_cap": market_cap,
            "rsi":        rsi,
            "macd_trend": macd_trend,
            "support":    support,
            "resistance": resistance,
        }
    except Exception as e:
        print(f"[Yahoo xato] {ticker}: {e}")
        return {}

def format_number(n) -> str:
    n = float(n or 0)
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n/1_000:.2f}K"
    return str(round(n, 2))

# ── Signal filtri ─────────────────────────────────────────────────────────────
def is_strong_signal(d: dict) -> tuple:
    reasons = []
    if d["rvol"] > 0 and d["rvol"] < MIN_RVOL:
        reasons.append(f"RVol past ({d['rvol']} < {MIN_RVOL})")
    if d["rsi"] > 0 and (d["rsi"] < RSI_MIN or d["rsi"] > RSI_MAX):
        reasons.append(f"RSI chegaradan tashqari ({d['rsi']})")
    if reasons:
        return False, " | ".join(reasons)
    return True, "OK"

# ── Xabar yasash ──────────────────────────────────────────────────────────────
def build_message(ticker: str, scanner_name: str) -> tuple:
    d = get_stock_info(ticker)
    if not d or d["price"] == 0:
        print(f"[Ma'lumot yo'q] {ticker}")
        return "", False, "Ma'lumot olinmadi"

    passed, reason = is_strong_signal(d)
    if not passed:
        return "", False, reason

    arrow   = "🟢" if d["change_pct"] >= 0 else "🔴"
    cap_str = format_number(d["market_cap"]) if d["market_cap"] else "N/A"
    vol_str = format_number(d["volume"])
    avg_str = format_number(d["avg_volume"])

    rsi = d["rsi"]
    if rsi >= 70:
        rsi_label = f"{rsi} ⚠️ Overbought"
    elif 0 < rsi <= 30:
        rsi_label = f"{rsi} ⚠️ Oversold"
    elif rsi > 0:
        rsi_label = str(rsi)
    else:
        rsi_label = "N/A"

    msg = (
        f"🧠 <b>Algorithm:</b> {scanner_name}\n"
        f"📌 <b>Ticker:</b> <code>{ticker}</code>\n"
        f"🏢 <b>Company:</b> {d['company']}\n"
        f"🏭 <b>Sector:</b> {d['sector']}\n"
        f"💰 <b>Price:</b> ${d['price']:.2f}\n"
        f"📊 <b>% Change:</b> {arrow} {d['change_pct']:+.2f}%\n"
        f"📉 <b>Yesterday Vol:</b> {avg_str}\n"
        f"📈 <b>Current Vol:</b> {vol_str}\n"
        f"⚡ <b>RVol:</b> {d['rvol']}\n"
        f"📊 <b>Market Cap:</b> {cap_str}\n"
        f"〰️ <b>RSI (14):</b> {rsi_label}\n"
        f"📉 <b>MACD:</b> {d['macd_trend']}\n"
        f"🎯 <b>Support:</b> ${d['support']} | <b>Resistance:</b> ${d['resistance']}\n"
        f"🕐 <b>Time:</b> {datetime.now().strftime('%H:%M, %d-%b-%Y')}"
    )
    return msg, True, "OK"

# ── Finviz grafik yuklash ─────────────────────────────────────────────────────
def download_finviz_chart(ticker: str) -> bytes | None:
    """Finviz chart rasmini yuklab qaytaradi."""
    url = f"https://charts.finviz.com/chart.ashx?t={ticker}&ty=c&ta=1&p=d&s=l&_={int(time.time())}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer":    "https://finviz.com/",
        "Accept":     "image/png,image/*,*/*",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        # PNG ekanligini tekshiramiz
        if resp.content[:4] == b'\x89PNG':
            return resp.content
        print(f"[Grafik] PNG emas ({len(resp.content)} bayt)")
        return None
    except Exception as e:
        print(f"[Grafik yuklab xato] {ticker}: {e}")
        return None

# ── Telegram ─────────────────────────────────────────────────────────────────
def send_telegram_photo(caption: str, ticker: str):
    img_bytes = download_finviz_chart(ticker)

    if img_bytes:
        # Rasmni fayl sifatida yuboramiz
        try:
            url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            resp = requests.post(url,
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "HTML"},
                files={"photo": (f"{ticker}.png", img_bytes, "image/png")},
                timeout=20
            )
            if resp.ok:
                return
            print(f"[Telegram photo xato] {resp.text}")
        except Exception as e:
            print(f"[Telegram photo xato] {e}")

    # Grafik chiqmasa — faqat matn yuboradi
    send_telegram_text(caption)

def send_telegram_text(text: str):
    url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       text,
        "parse_mode": "HTML",
    }, timeout=15)
    if not resp.ok:
        print(f"[Telegram matn xato] {resp.text}")

# ── Email o'qish ──────────────────────────────────────────────────────────────
def extract_tickers_and_scanner(subject: str, body: str):
    text = subject

    m = re.search(r"added to ([^:]+?)(?:\s*:|\.\s*$|\s+oldin\b)", text, re.IGNORECASE)
    if m:
        scanner_name = m.group(1).strip()
    else:
        m2 = re.search(r"added to (.+?)(?:\.|$)", text, re.IGNORECASE)
        scanner_name = m2.group(1).strip() if m2 else "TOS Scanner"

    tickers = []
    m = re.search(r"symbols?\s*:\s*([A-Z][A-Z ,]*?)\s+(?:was|were)\b", text, re.IGNORECASE)
    if m:
        raw = m.group(1)
        tickers = [t.strip() for t in raw.split(",") if re.match(r"^[A-Z]{1,5}$", t.strip())]

    if not tickers:
        m2 = re.search(r":\s*([A-Z]{1,5}(?:,\s*[A-Z]{1,5})+)\s*$", text)
        if m2:
            raw = m2.group(1)
            tickers = [t.strip() for t in raw.split(",") if re.match(r"^[A-Z]{1,5}$", t.strip())]

    return list(dict.fromkeys(tickers)), scanner_name

def check_email():
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
            raw     = msg_data[0][1]
            msg     = email.message_from_bytes(raw)
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
                print("[Skip] Following list email otkazib yuborildi")
                ALREADY_SENT.add(msg_id)
                save_sent_id(msg_id)
                continue

            tickers, scanner_name = extract_tickers_and_scanner(subject, body)
            print(f"[Email] Tickers: {tickers}, Scanner: {scanner_name}")

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

        mail.logout()

    except Exception as e:
        print(f"[Xato] {e}")

# ── Asosiy tsikl ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 TOS → Telegram bot v4 ishga tushdi!")
    print(f"   Gmail: {GMAIL_USER}")
    print(f"   Kanal: {TELEGRAM_CHAT_ID}")
    print(f"   Har {CHECK_INTERVAL}s tekshiradi...")
    print(f"   Filter: RVol>={MIN_RVOL}, RSI {RSI_MIN}-{RSI_MAX}\n")

    while True:
        check_email()
        time.sleep(CHECK_INTERVAL)
