"""
TOS Alert → Telegram Bot (v2 — RSI, MACD, Support/Resistance, Signal Filter)
alerts@thinkorswim.com emaillarini o'qib, texnik tahlil bilan Telegram kanaliga yuboradi.

O'rnatish:
    pip install requests yfinance python-dotenv pandas

Muhit o'zgaruvchilari (.env fayl):
    GMAIL_USER=sizning@gmail.com
    GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
    TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
    TELEGRAM_CHAT_ID=-100123456789
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
CHECK_INTERVAL   = 15          # 15 sekundda bir tekshiradi (tezroq signal)

# Signal filtri minimal talablar
MIN_RVOL         = 1.0         # RVol kamida 1.0
MIN_CHANGE_PCT   = -10.0       # % o'zgarish (manfiy ham o'tsin)
RSI_MIN          = 30          # RSI min
RSI_MAX          = 80          # RSI max

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
    """RSI hisoblaydi."""
    try:
        delta = closes.diff()
        gain  = delta.clip(lower=0).rolling(period).mean()
        loss  = (-delta.clip(upper=0)).rolling(period).mean()
        rs    = gain / loss
        rsi   = 100 - (100 / (1 + rs))
        return round(float(rsi.iloc[-1]), 1)
    except Exception:
        return 0.0

def calc_macd(closes: pd.Series):
    """MACD va signal liniyasini hisoblaydi. (macd_val, signal_val, trend)"""
    try:
        ema12  = closes.ewm(span=12, adjust=False).mean()
        ema26  = closes.ewm(span=26, adjust=False).mean()
        macd   = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        macd_val   = round(float(macd.iloc[-1]), 3)
        signal_val = round(float(signal.iloc[-1]), 3)
        trend = "Bullish ↑" if macd_val > signal_val else "Bearish ↓"
        return macd_val, signal_val, trend
    except Exception:
        return 0.0, 0.0, "N/A"

def calc_support_resistance(hist: pd.DataFrame):
    """52 haftalik high/low asosida support va resistance."""
    try:
        high_52w = round(float(hist["High"].max()), 2)
        low_52w  = round(float(hist["Low"].min()), 2)
        return low_52w, high_52w
    except Exception:
        return 0.0, 0.0

# ── Yahoo Finance ma'lumotlari ───────────────────────────────────────────────
def get_stock_info(ticker: str) -> dict:
    """Ticker bo'yicha to'liq ma'lumot + texnik indikatorlar."""
    try:
        stock = yf.Ticker(ticker)
        info  = stock.info
        hist  = stock.history(period="1y")

        price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("navPrice")
            or 0
        )
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose") or 0
        change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0
        volume     = info.get("volume") or info.get("regularMarketVolume") or 0
        avg_vol    = info.get("averageVolume") or 0
        rvol       = round(volume / avg_vol, 2) if avg_vol else 0
        market_cap = info.get("marketCap") or 0
        sector     = info.get("sector") or "N/A"
        company    = info.get("longName") or info.get("shortName") or ticker

        # Texnik indikatorlar
        closes = hist["Close"]
        rsi    = calc_rsi(closes)
        macd_val, signal_val, macd_trend = calc_macd(closes)
        support, resistance = calc_support_resistance(hist)

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
            "macd":       macd_val,
            "macd_trend": macd_trend,
            "support":    support,
            "resistance": resistance,
        }
    except Exception as e:
        print(f"[Yahoo xato] {ticker}: {e}")
        return {}

def format_number(n: float) -> str:
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n/1_000:.2f}K"
    return str(round(n, 2))

# ── Signal filtri ────────────────────────────────────────────────────────────
def is_strong_signal(d: dict) -> tuple:
    """
    Signalni filtrlaydi. (o'tdi: bool, sabab: str)
    """
    reasons = []

    if d["rvol"] < MIN_RVOL:
        reasons.append(f"RVol past ({d['rvol']} < {MIN_RVOL})")

    if d["rsi"] > 0 and (d["rsi"] < RSI_MIN or d["rsi"] > RSI_MAX):
        reasons.append(f"RSI haddan tashqari ({d['rsi']})")

    if reasons:
        return False, " | ".join(reasons)
    return True, "OK"

# ── Signal xabari yasash ──────────────────────────────────────────────────────
def build_message(ticker: str, scanner_name: str) -> tuple:
    """
    (caption, passed, skip_reason) qaytaradi.
    passed=False bo'lsa signal filtrdan o'tmagan.
    """
    d = get_stock_info(ticker)
    if not d:
        return f"<b>🔔 {ticker}</b>\n<i>Ma'lumot olinmadi</i>", False, "Ma'lumot yo'q"

    passed, reason = is_strong_signal(d)
    if not passed:
        return "", False, reason

    arrow   = "🟢" if d["change_pct"] >= 0 else "🔴"
    cap_str = format_number(d["market_cap"]) if d["market_cap"] else "N/A"
    vol_str = format_number(d["volume"])
    avg_str = format_number(d["avg_volume"])

    # RSI holati
    if d["rsi"] >= 70:
        rsi_label = f"{d['rsi']} ⚠️ Overbought"
    elif d["rsi"] <= 30:
        rsi_label = f"{d['rsi']} ⚠️ Oversold"
    else:
        rsi_label = str(d["rsi"])

    msg = (
        f"🧠 <b>Algorithm:</b> {scanner_name}\n"
        f"📌 <b>Ticker:</b> <code>{ticker}</code>\n"
        f"🏢 <b>Company:</b> {d['company']}\n"
        f"🏭 <b>Sector:</b> {d['sector']}\n"
        f"💰 <b>Price:</b> ${d['price']:.4f}\n"
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

# ── Telegram ─────────────────────────────────────────────────────────────────
def send_telegram_photo(caption: str, ticker: str):
    """Finviz grafikini Telegramga yuboradi (2 usul)."""
    chart_url = f"https://charts.finviz.com/chart.ashx?t={ticker}&ty=c&ta=1&p=d&s=l"

    # 1-usul: URL bilan
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "photo": chart_url,
            "caption": caption,
            "parse_mode": "HTML",
        }, timeout=15)
        if resp.ok:
            return
        print(f"[URL usuli ishlamadi] {resp.text}")
    except Exception as e:
        print(f"[URL usuli xato] {e}")

    # 2-usul: Rasmni yuklab fayl sifatida
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://finviz.com/"}
        img_resp = requests.get(chart_url, headers=headers, timeout=15)
        img_resp.raise_for_status()
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        resp = requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "caption": caption,
            "parse_mode": "HTML",
        }, files={"photo": (f"{ticker}.png", img_resp.content, "image/png")}, timeout=20)
        if not resp.ok:
            print(f"[Fayl usuli xato] {resp.text}")
            send_telegram_text(caption)
    except Exception as e:
        print(f"[Grafik xato] {ticker}: {e}")
        send_telegram_text(caption)

def send_telegram_text(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }, timeout=15)
    if not resp.ok:
        print(f"[Telegram matn xato] {resp.text}")

# ── Email o'qish ──────────────────────────────────────────────────────────────
def extract_tickers_and_scanner(subject: str, body: str):
    text = subject

    scanner_match = re.search(r"added to ([^:]+?)(?:\s*:|\.\s*$|\s+oldin\b)", text, re.IGNORECASE)
    if scanner_match:
        scanner_name = scanner_match.group(1).strip()
    else:
        scanner_match2 = re.search(r"added to (.+?)(?:\.|$)", text, re.IGNORECASE)
        scanner_name = scanner_match2.group(1).strip() if scanner_match2 else "TOS Scanner"

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
                time.sleep(1)

            ALREADY_SENT.add(msg_id)
            save_sent_id(msg_id)

        mail.logout()

    except Exception as e:
        print(f"[Xato] {e}")

# ── Asosiy tsikl ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 TOS → Telegram bot v2 ishga tushdi!")
    print(f"   Gmail: {GMAIL_USER}")
    print(f"   Kanal: {TELEGRAM_CHAT_ID}")
    print(f"   Har {CHECK_INTERVAL}s tekshiradi...")
    print(f"   Filter: RVol>={MIN_RVOL}, RSI {RSI_MIN}-{RSI_MAX}\n")

    while True:
        check_email()
        time.sleep(CHECK_INTERVAL)
