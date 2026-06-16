"""
TOS Alert → Telegram Bot (v3)
alerts@thinkorswim.com emaillarini o'qib, Finviz + texnik tahlil bilan Telegram kanaliga yuboradi.
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

# ── Finviz dan ma'lumot olish (asosiy manba) ─────────────────────────────────
def get_finviz_data(ticker: str) -> dict:
    """Finviz screener dan real-time ma'lumot scraping."""
    try:
        url = f"https://finviz.com/quote.ashx?t={ticker}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://finviz.com/"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        html = resp.text

        def extract(label):
            pattern = rf'{re.escape(label)}</td>\s*<td[^>]*>([^<]+)<'
            m = re.search(pattern, html)
            return m.group(1).strip() if m else "N/A"

        price_match = re.search(r'"price"[^>]*>([0-9,.]+)<', html)
        if not price_match:
            price_match = re.search(r'class="quote-price"[^>]*>([0-9,.]+)', html)
        price = float(price_match.group(1).replace(",", "")) if price_match else 0

        change_match = re.search(r'([+-]?\d+\.?\d*%)\s*</span>', html)
        change_pct_str = change_match.group(1) if change_match else "0%"
        change_pct = float(change_pct_str.replace("%", "").replace("+", "")) if change_match else 0

        company_match = re.search(r'<h2[^>]*>\s*<a[^>]*>([^<]+)</a>', html)
        company = company_match.group(1).strip() if company_match else ticker

        sector  = extract("Sector")
        rvol_str = extract("Rel Volume")
        volume_str = extract("Volume")
        avg_vol_str = extract("Avg Volume")
        market_cap_str = extract("Market Cap")
        rsi_str = extract("RSI (14)")

        def parse_num(s):
            if s == "N/A" or not s:
                return 0
            s = s.replace(",", "")
            mult = 1
            if s.endswith("B"):
                mult = 1_000_000_000
                s = s[:-1]
            elif s.endswith("M"):
                mult = 1_000_000
                s = s[:-1]
            elif s.endswith("K"):
                mult = 1_000
                s = s[:-1]
            try:
                return float(s) * mult
            except:
                return 0

        rvol = float(rvol_str) if rvol_str != "N/A" else 0
        rsi  = float(rsi_str) if rsi_str != "N/A" else 0

        return {
            "company":    company,
            "sector":     sector,
            "price":      price,
            "change_pct": change_pct,
            "volume":     parse_num(volume_str),
            "avg_volume": parse_num(avg_vol_str),
            "rvol":       rvol,
            "market_cap": parse_num(market_cap_str),
            "rsi":        rsi,
            "source":     "finviz"
        }
    except Exception as e:
        print(f"[Finviz xato] {ticker}: {e}")
        return {}

# ── Yahoo Finance (zaxira + MACD, S/R) ──────────────────────────────────────
def calc_rsi(closes: pd.Series, period: int = 14) -> float:
    try:
        if len(closes) < period + 1:
            return 0.0
        delta = closes.diff().dropna()
        gain  = delta.clip(lower=0).rolling(period).mean()
        loss  = (-delta.clip(upper=0)).rolling(period).mean()
        rs    = gain / loss
        rsi   = 100 - (100 / (1 + rs))
        val   = float(rsi.dropna().iloc[-1])
        return round(val, 1) if not pd.isna(val) else 0.0
    except:
        return 0.0

def calc_macd(closes: pd.Series):
    try:
        if len(closes) < 26:
            return 0.0, 0.0, "N/A"
        ema12  = closes.ewm(span=12, adjust=False).mean()
        ema26  = closes.ewm(span=26, adjust=False).mean()
        macd   = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        macd_val   = round(float(macd.iloc[-1]), 3)
        signal_val = round(float(signal.iloc[-1]), 3)
        trend = "Bullish ↑" if macd_val > signal_val else "Bearish ↓"
        return macd_val, signal_val, trend
    except:
        return 0.0, 0.0, "N/A"

def get_technical(ticker: str) -> dict:
    """Yahoo Finance dan MACD va Support/Resistance."""
    try:
        stock = yf.Ticker(ticker)
        hist  = stock.history(period="1y")
        if hist.empty:
            return {"macd_trend": "N/A", "support": 0, "resistance": 0}
        closes = hist["Close"]
        _, _, macd_trend = calc_macd(closes)
        support    = round(float(hist["Low"].min()), 2)
        resistance = round(float(hist["High"].max()), 2)
        return {
            "macd_trend": macd_trend,
            "support":    support,
            "resistance": resistance,
        }
    except Exception as e:
        print(f"[Yahoo xato] {ticker}: {e}")
        return {"macd_trend": "N/A", "support": 0, "resistance": 0}

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
    reasons = []
    if d["rvol"] > 0 and d["rvol"] < MIN_RVOL:
        reasons.append(f"RVol past ({d['rvol']} < {MIN_RVOL})")
    if d["rsi"] > 0 and (d["rsi"] < RSI_MIN or d["rsi"] > RSI_MAX):
        reasons.append(f"RSI haddan ({d['rsi']})")
    if reasons:
        return False, " | ".join(reasons)
    return True, "OK"

# ── Xabar yasash ─────────────────────────────────────────────────────────────
def build_message(ticker: str, scanner_name: str) -> tuple:
    # Finviz dan asosiy ma'lumot
    d = get_finviz_data(ticker)
    if not d:
        return "", False, "Ma'lumot yo'q"

    passed, reason = is_strong_signal(d)
    if not passed:
        return "", False, reason

    # Yahoo dan texnik ma'lumot
    tech = get_technical(ticker)

    arrow   = "🟢" if d["change_pct"] >= 0 else "🔴"
    cap_str = format_number(d["market_cap"]) if d["market_cap"] else "N/A"
    vol_str = format_number(d["volume"])
    avg_str = format_number(d["avg_volume"])

    rsi = d["rsi"]
    if rsi >= 70:
        rsi_label = f"{rsi} ⚠️ Overbought"
    elif rsi > 0 and rsi <= 30:
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
        f"💰 <b>Price:</b> ${d['price']:.4f}\n"
        f"📊 <b>% Change:</b> {arrow} {d['change_pct']:+.2f}%\n"
        f"📉 <b>Yesterday Vol:</b> {avg_str}\n"
        f"📈 <b>Current Vol:</b> {vol_str}\n"
        f"⚡ <b>RVol:</b> {d['rvol']}\n"
        f"📊 <b>Market Cap:</b> {cap_str}\n"
        f"〰️ <b>RSI (14):</b> {rsi_label}\n"
        f"📉 <b>MACD:</b> {tech['macd_trend']}\n"
        f"🎯 <b>Support:</b> ${tech['support']} | <b>Resistance:</b> ${tech['resistance']}\n"
        f"🕐 <b>Time:</b> {datetime.now().strftime('%H:%M, %d-%b-%Y')}"
    )
    return msg, True, "OK"

# ── Finviz grafik URL ─────────────────────────────────────────────────────────
def finviz_chart_url(ticker: str) -> str:
    """Cache busting bilan Finviz grafik URL."""
    ts = int(time.time())
    return f"https://charts.finviz.com/chart.ashx?t={ticker}&ty=c&ta=1&p=d&s=l&_={ts}"

# ── Telegram ─────────────────────────────────────────────────────────────────
def send_telegram_photo(caption: str, ticker: str):
    chart_url = finviz_chart_url(ticker)

    # 1-usul: rasmni yuklab yuborish (cache bypass)
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://finviz.com/"
        }
        img_resp = requests.get(chart_url, headers=headers, timeout=15)
        img_resp.raise_for_status()
        url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        resp = requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "caption": caption,
            "parse_mode": "HTML",
        }, files={"photo": (f"{ticker}.png", img_resp.content, "image/png")}, timeout=20)
        if resp.ok:
            return
        print(f"[Fayl usuli xato] {resp.text}")
    except Exception as e:
        print(f"[Grafik yuklab xato] {e}")

    # 2-usul: URL bilan
    try:
        url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "photo": chart_url,
            "caption": caption,
            "parse_mode": "HTML",
        }, timeout=15)
        if resp.ok:
            return
    except Exception as e:
        print(f"[URL usuli xato] {e}")

    # 3-usul: faqat matn
    send_telegram_text(caption)

def send_telegram_text(text: str):
    url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
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
                time.sleep(2)

            ALREADY_SENT.add(msg_id)
            save_sent_id(msg_id)

        mail.logout()

    except Exception as e:
        print(f"[Xato] {e}")

# ── Asosiy tsikl ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 TOS → Telegram bot v3 ishga tushdi!")
    print(f"   Gmail: {GMAIL_USER}")
    print(f"   Kanal: {TELEGRAM_CHAT_ID}")
    print(f"   Har {CHECK_INTERVAL}s tekshiradi...")
    print(f"   Filter: RVol>={MIN_RVOL}, RSI {RSI_MIN}-{RSI_MAX}\n")

    while True:
        check_email()
        time.sleep(CHECK_INTERVAL)
