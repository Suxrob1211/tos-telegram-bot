"""
TOS Alert → Telegram Bot
alerts@thinkorswim.com emaillarini o'qib, Finviz grafik + Yahoo Finance ma'lumotlari
bilan Telegram kanaliga yuboradi.

O'rnatish:
    pip install requests yfinance python-dotenv

Muhit o'zgaruvchilari (.env fayl):
    GMAIL_USER=sizning@gmail.com
    GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
    TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
    TELEGRAM_CHAT_ID=@sizning_kanal yoki -100123456789
"""

import imaplib
import email
import time
import re
import os
import requests
import yfinance as yf
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# ── Sozlamalar ──────────────────────────────────────────────────────────────
GMAIL_USER       = os.getenv("GMAIL_USER")
GMAIL_APP_PASS   = os.getenv("GMAIL_APP_PASSWORD")
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TOS_SENDER       = "alerts@thinkorswim.com"
CHECK_INTERVAL   = 60          # sekundda bir tekshiradi

# FIX #3: ALREADY_SENT faylga saqlanadi — bot qayta ishga tushsa ham eslab qoladi
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

# ── Telegram ─────────────────────────────────────────────────────────────────
# FIX #2: Finviz hotlink himoyasi tufayli sendPhoto ishlamaydi.
# Grafik rasmini avval yuklab, keyin sendPhoto (file sifatida) yuboramiz.
def send_telegram_photo(caption: str, ticker: str):
    """Finviz grafikini yuklab, Telegramga fayl sifatida yuboradi."""
    chart_url = (
        f"https://finviz.com/chart.ashx?"
        f"t={ticker}&ty=c&ta=1&p=d&s=l"
        f"&cache={int(time.time())}"
    )
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://finviz.com/",
    }
    try:
        img_resp = requests.get(chart_url, headers=headers, timeout=15)
        img_resp.raise_for_status()

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        files = {"photo": (f"{ticker}.png", img_resp.content, "image/png")}
        data  = {
            "chat_id":    TELEGRAM_CHAT_ID,
            "caption":    caption,
            "parse_mode": "HTML",
        }
        resp = requests.post(url, data=data, files=files, timeout=20)
        if not resp.ok:
            print(f"[Telegram xato] {resp.text}")
            send_telegram_text(caption)   # grafik chiqmasa matn yuboradi
    except Exception as e:
        print(f"[Grafik xato] {ticker}: {e}")
        send_telegram_text(caption)

def send_telegram_text(text: str):
    """Faqat matn yuboradi."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       text,
        "parse_mode": "HTML",
    }
    resp = requests.post(url, json=payload, timeout=15)
    if not resp.ok:
        print(f"[Telegram matn xato] {resp.text}")

# ── Yahoo Finance ma'lumotlari ───────────────────────────────────────────────
def get_stock_info(ticker: str) -> dict:
    """Ticker bo'yicha asosiy ma'lumotlarni oladi."""
    try:
        stock = yf.Ticker(ticker)
        info  = stock.info

        # FIX #5: price None bo'lmasligi uchun bir nechta fallback
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

        return {
            "company":    company,
            "sector":     sector,
            "price":      price,
            "change_pct": change_pct,
            "volume":     volume,
            "avg_volume": avg_vol,
            "rvol":       rvol,
            "market_cap": market_cap,
        }
    except Exception as e:
        print(f"[Yahoo xato] {ticker}: {e}")
        return {}

def format_number(n: float) -> str:
    """Sonni o'qilishi oson formatga o'tkazadi: 1500000 → 1.50M"""
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n/1_000:.2f}K"
    return str(round(n, 2))

# ── Signal xabari yasash ──────────────────────────────────────────────────────
def build_message(ticker: str, scanner_name: str) -> str:
    """Ticker uchun Telegram xabarini yasaydi."""
    d = get_stock_info(ticker)
    if not d:
        return f"<b>🔔 {ticker}</b>\n<i>Ma'lumot olinmadi</i>"

    arrow   = "🟢" if d["change_pct"] >= 0 else "🔴"
    cap_str = format_number(d["market_cap"]) if d["market_cap"] else "N/A"
    vol_str = format_number(d["volume"])
    avg_str = format_number(d["avg_volume"])

    # FIX #6: <code>abc</code> test qoldig'i olib tashlandi
    msg = (
        f"🧠 <b>Algorithm:</b> {scanner_name}\n"
        f"📌 <b>Ticker:</b> {ticker}\n"
        f"🏢 <b>Company:</b> {d['company']}\n"
        f"🏭 <b>Sector:</b> {d['sector']}\n"
        f"💰 <b>Price:</b> ${d['price']:.4f}\n"
        f"📊 <b>% Change:</b> {arrow} {d['change_pct']:+.2f}%\n"
        f"📉 <b>Yesterday Vol:</b> {avg_str}\n"
        f"📈 <b>Current Vol:</b> {vol_str}\n"
        f"⚡ <b>RVol:</b> {d['rvol']}\n"
        f"📊 <b>Market Cap:</b> {cap_str}\n"
        f"🕐 <b>Time:</b> {datetime.now().strftime('%H:%M, %d-%b-%Y')}"
    )
    return msg

# ── Email o'qish ──────────────────────────────────────────────────────────────
def extract_tickers_and_scanner(subject: str, body: str):
    """
    Emaildan ticker(lar) va scanner nomini ajratib oladi.
    Formatlar:
      'Alert: New symbol: CRWD was added to trend + breakout + volume'
      'Alert: New symbols: COP, CVX, MGY were added to pullback.'
    """
    text = subject

    # Scanner nomi
    scanner_match = re.search(r"added to ([^:]+?)(?:\s*:|\.\s*$|\s+oldin\b)", text, re.IGNORECASE)
    if scanner_match:
        scanner_name = scanner_match.group(1).strip()
    else:
        scanner_match2 = re.search(r"added to (.+?)(?:\.|$)", text, re.IGNORECASE)
        scanner_name = scanner_match2.group(1).strip() if scanner_match2 else "TOS Scanner"

    tickers = []

    # Format A/B: "New symbol(s): TICKER(S) was/were added to..."
    m = re.search(r"symbols?\s*:\s*([A-Z][A-Z ,]*?)\s+(?:was|were)\b", text, re.IGNORECASE)
    if m:
        raw = m.group(1)
        tickers = [t.strip() for t in raw.split(",") if re.match(r"^[A-Z]{1,5}$", t.strip())]

    # Format C: "...SCANNER : TICKER1, TICKER2" — oxirida ticker ro'yxati
    if not tickers:
        m2 = re.search(r":\s*([A-Z]{1,5}(?:,\s*[A-Z]{1,5})+)\s*$", text)
        if m2:
            raw = m2.group(1)
            tickers = [t.strip() for t in raw.split(",") if re.match(r"^[A-Z]{1,5}$", t.strip())]

    return list(dict.fromkeys(tickers)), scanner_name

def check_email():
    """Gmail IMAP orqali yangi TOS alertlarni tekshiradi."""
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_APP_PASS)
        mail.select("inbox")

        # FIX #4: IMAP SINCE faqat sana qabul qiladi, vaqt emas.
        # Bugungi emaillarni olamiz, Message-ID orqali takrorni oldini olamiz.
        since = datetime.now().strftime("%d-%b-%Y")
        _, data = mail.search(None, f'(UNSEEN FROM "{TOS_SENDER}" SINCE "{since}")')

        ids = data[0].split()
        print(f"[Email] {len(ids)} ta yangi TOS alert")

        for eid in ids:
            _, msg_data = mail.fetch(eid, "(RFC822)")
            raw         = msg_data[0][1]
            msg         = email.message_from_bytes(raw)
            subject     = msg.get("Subject", "")
            msg_id      = msg.get("Message-ID", str(eid))

            if msg_id in ALREADY_SENT:
                continue

            # Body olish
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

            print(f"[Email] Subject: {subject}")

            # FIX #1: takroriy `import re` olib tashlandi — yuqorida bir marta import qilingan
            if not re.search(r"New symbols?\s*:", subject, re.IGNORECASE):
                print("[Skip] Following list email otkazib yuborildi")
                ALREADY_SENT.add(msg_id)
                save_sent_id(msg_id)
                continue

            print(f"[Email] Body preview: {body[:120]}")

            tickers, scanner_name = extract_tickers_and_scanner(subject, body)
            print(f"[Email] Tickers: {tickers}, Scanner: {scanner_name}")

            for ticker in tickers:
                caption = build_message(ticker, scanner_name)
                send_telegram_photo(caption, ticker)
                print(f"[Telegram] {ticker} yuborildi ✅")
                time.sleep(1)   # flood limit

            ALREADY_SENT.add(msg_id)
            save_sent_id(msg_id)

        mail.logout()

    except Exception as e:
        print(f"[Xato] {e}")

# ── Asosiy tsikl ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 TOS → Telegram bot ishga tushdi!")
    print(f"   Gmail: {GMAIL_USER}")
    print(f"   Kanal: {TELEGRAM_CHAT_ID}")
    print(f"   Har {CHECK_INTERVAL}s tekshiradi...\n")

    while True:
        check_email()
        time.sleep(CHECK_INTERVAL)
