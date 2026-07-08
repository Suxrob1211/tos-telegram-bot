"""
TOS Signal Tracker Bot
"ThinkorSwim Signal" kanalidagi signallarni o'qib, ularning natijasini kuzatadi
va "Signals Natija" kanaliga kunlik/oylik hisobot yuboradi.

Bu bot Gmail bilan ishlamaydi — faqat Telegram orqali signal xabarlarini
o'qiydi (getUpdates API) va Yahoo Finance orqali narxlarni kuzatadi.

Muhit o'zgaruvchilari (.env yoki Railway Variables):
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    SIGNAL_CHAT_ID=-1003942860549      (ThinkorSwim Signal kanali ID si)
    RESULTS_CHAT_ID=-1004358677830   (Signals Natija kanali ID si)
"""

import time
import re
import os
import json
import requests
import yfinance as yf
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN")
SIGNAL_CHAT_ID   = os.getenv("SIGNAL_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")   # "ThinkorSwim Signal" kanali
RESULTS_CHAT_ID  = os.getenv("RESULTS_CHAT_ID", "-1004358677830")  # "Signals Natija" kanali

CHECK_INTERVAL   = 60     # 60 sekundda yangi xabarlarni tekshiradi

# ── Signal tracking sozlamalari ───────────────────────────────────────────────
TARGET_PCT     = 10.0   # +10% ga yetsa - foydada yopiladi
STOP_LOSS_PCT  = -5.0   # -5% ga tushsa - zararda yopiladi
MAX_HOLD_DAYS  = 30     # 30 kundan keyin - muddati tugadi

SIGNALS_DB                = "signals_db.json"
LAST_UPDATE_ID_FILE       = "last_update_id.txt"
LAST_MONTHLY_REPORT_FILE  = "last_monthly_report.txt"


# ── Signal DB: saqlash va o'qish ──────────────────────────────────────────────
def load_signals_db() -> list:
    if not os.path.exists(SIGNALS_DB):
        return []
    try:
        with open(SIGNALS_DB, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[DB xato] o'qishda: {e}")
        return []


def save_signals_db(signals: list):
    try:
        with open(SIGNALS_DB, "w") as f:
            json.dump(signals, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[DB xato] yozishda: {e}")


def load_last_update_id() -> int:
    if not os.path.exists(LAST_UPDATE_ID_FILE):
        return 0
    try:
        with open(LAST_UPDATE_ID_FILE, "r") as f:
            return int(f.read().strip() or 0)
    except Exception:
        return 0


def save_last_update_id(update_id: int):
    with open(LAST_UPDATE_ID_FILE, "w") as f:
        f.write(str(update_id))


def is_ticker_already_tracked_today(ticker: str) -> bool:
    """Bir xil ticker bir kunda 2 marta qo'shilib ketmasligi uchun tekshiradi."""
    signals = load_signals_db()
    today = datetime.now().strftime("%Y-%m-%d")
    for sig in signals:
        if sig["ticker"] == ticker and sig["entry_date"] == today and sig["status"] == "open":
            return True
    return False


def add_signal_to_tracking(ticker: str, scanner_name: str, entry_price: float):
    """Yangi signalni kuzatuv bazasiga qo'shadi."""
    if entry_price <= 0:
        return
    if is_ticker_already_tracked_today(ticker):
        print(f"[Tracking] {ticker} bugun allaqachon kuzatuvda, o'tkazib yuborildi")
        return

    signals = load_signals_db()
    signals.append({
        "ticker": ticker,
        "scanner": scanner_name,
        "entry_price": entry_price,
        "entry_date": datetime.now().strftime("%Y-%m-%d"),
        "entry_datetime": datetime.now().isoformat(),
        "status": "open",
        "exit_price": None,
        "exit_date": None,
        "pct_change": None,
    })
    save_signals_db(signals)
    print(f"[Tracking] {ticker} kuzatuvga qo'shildi (kirish: ${entry_price:.2f}, scanner: {scanner_name})")


# ── Telegram xabarlarini o'qish (getUpdates) ─────────────────────────────────
def parse_signal_message(text: str) -> dict | None:
    """
    Bot yuborgan signal xabaridan ticker, price, scanner ni ajratib oladi.
    Kutilayotgan format (mavjud Windows bot formatiga mos):

    🧠 Algorithm: trend + breakout + volume
    📌 Ticker: KLAC
    ...
    💰 Price: $2136.81
    """
    if not text or "Ticker:" not in text:
        return None

    ticker_match   = re.search(r"Ticker:\s*<?code?>?\s*([A-Z]{1,6})", text)
    price_match    = re.search(r"Price:\s*\$?([\d,]+\.?\d*)", text)
    scanner_match  = re.search(r"Algorithm:\s*([^\n]+)", text)

    if not ticker_match or not price_match:
        return None

    ticker  = ticker_match.group(1).strip()
    price   = float(price_match.group(1).replace(",", ""))
    scanner = scanner_match.group(1).strip() if scanner_match else "Noma'lum"

    return {"ticker": ticker, "price": price, "scanner": scanner}


def poll_telegram_updates():
    """Telegram getUpdates orqali kanaldagi yangi postlarni oladi."""
    last_id = load_last_update_id()
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"offset": last_id + 1, "timeout": 10, "allowed_updates": '["channel_post"]'}

    try:
        resp = requests.get(url, params=params, timeout=20)

        print("=" * 60)
        print("HTTP Status:", resp.status_code)
        print("Response:")
        print(resp.text)
        print("=" * 60)
        
        data = resp.json()
        
    except Exception as e:
        print(f"[Telegram poll xato] {e}")
        return

    if not data.get("ok"):
        print(f"[Telegram poll xato] {data}")
        return

    updates = data.get("result", [])

    print(f"Updates soni: {len(updates)}")
    
    if updates:
        print(json.dumps(updates, indent=2, ensure_ascii=False))

    if not updates:    
        return

    new_signals_count = 0
    for update in updates:
        update_id = update["update_id"]
        save_last_update_id(update_id)

        post = update.get("channel_post")
        if not post:
            continue

        chat_id = str(post.get("chat", {}).get("id", ""))
        if SIGNAL_CHAT_ID and chat_id != str(SIGNAL_CHAT_ID):
            continue

        # Rasm bilan kelgan xabarlarda matn "caption" da bo'ladi
        text = post.get("text") or post.get("caption") or ""

        parsed = parse_signal_message(text)
        if parsed:
            add_signal_to_tracking(parsed["ticker"], parsed["scanner"], parsed["price"])
            new_signals_count += 1

    if new_signals_count:
        print(f"[Poll] {new_signals_count} ta yangi signal kuzatuvga qo'shildi")


# ── Kunlik tekshiruv va hisobot ───────────────────────────────────────────────
def check_open_signals() -> dict:
    """
    Barcha 'open' signallarni tekshiradi:
    +10% -> profit, -5% -> loss, 30 kun -> expired.
    """
    signals = load_signals_db()
    closed_today = []
    still_open_list = []

    for sig in signals:
        if sig["status"] != "open":
            continue

        ticker = sig["ticker"]
        try:
            stock = yf.Ticker(ticker)
            info  = stock.info
            price = float(info.get("currentPrice") or info.get("regularMarketPrice") or 0.0)
        except Exception as e:
            print(f"[Tracking xato] {ticker}: {e}")
            still_open_list.append({**sig, "current_price": None, "current_pct": None})
            continue

        if price <= 0:
            still_open_list.append({**sig, "current_price": None, "current_pct": None})
            continue

        entry_price = sig["entry_price"]
        pct = (price - entry_price) / entry_price * 100

        entry_date = datetime.strptime(sig["entry_date"], "%Y-%m-%d")
        days_held  = (datetime.now() - entry_date).days

        new_status = None
        if pct >= TARGET_PCT:
            new_status = "profit"
        elif pct <= STOP_LOSS_PCT:
            new_status = "loss"
        elif days_held >= MAX_HOLD_DAYS:
            new_status = "expired"

        if new_status:
            sig["status"]     = new_status
            sig["exit_price"] = round(price, 2)
            sig["exit_date"]  = datetime.now().strftime("%Y-%m-%d")
            sig["pct_change"] = round(pct, 2)
            closed_today.append(sig)
            print(f"[Tracking] {ticker} yopildi: {new_status} ({pct:+.2f}%)")
        else:
            still_open_list.append({
                **sig, "current_price": round(price, 2),
                "current_pct": round(pct, 2), "days_held": days_held
            })

    save_signals_db(signals)
    return {"closed_today": closed_today, "still_open_list": still_open_list}


def send_telegram_text_to(text: str, chat_id: str):
    url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": chat_id, "text": text, "parse_mode": "HTML",
    }, timeout=15)
    if not resp.ok:
        print(f"[Telegram matn xato] {resp.text}")


def send_daily_tracking_report():
    """Kunlik natija xabarini 'Signals Natija' kanaliga yuboradi."""
    result = check_open_signals()
    closed = result["closed_today"]
    still_open_list = result["still_open_list"]

    if not closed and not still_open_list:
        return

    lines = [f"📅 <b>Kunlik hisobot — {datetime.now().strftime('%d-%b-%Y')}</b>\n"]

    if closed:
        lines.append(f"🔔 <b>Bugun yopilgan signallar ({len(closed)}):</b>")
        for sig in closed:
            emoji = "✅" if sig["status"] == "profit" else ("❌" if sig["status"] == "loss" else "⏱")
            status_text = {"profit": "Foydada", "loss": "Zararda", "expired": "Muddati tugadi"}[sig["status"]]
            lines.append(
                f"{emoji} <code>{sig['ticker']}</code> — {status_text} "
                f"({sig['pct_change']:+.2f}%) | Kirish: ${sig['entry_price']:.2f} → Chiqish: ${sig['exit_price']:.2f} "
                f"| Scanner: {sig['scanner']}"
            )
        lines.append("")

    if still_open_list:
        sorted_open = sorted(
            still_open_list,
            key=lambda s: s["current_pct"] if s["current_pct"] is not None else -999,
            reverse=True
        )
        lines.append(f"📊 <b>Hozir kuzatilayotgan signallar ({len(sorted_open)} ta):</b>")
        for sig in sorted_open:
            if sig["current_pct"] is None:
                lines.append(f"⚪ <code>{sig['ticker']}</code> — ma'lumot olinmadi | Scanner: {sig['scanner']}")
                continue
            arrow = "🟢" if sig["current_pct"] >= 0 else "🔴"
            lines.append(
                f"{arrow} <code>{sig['ticker']}</code> {sig['current_pct']:+.2f}% "
                f"| ${sig['entry_price']:.2f} → ${sig['current_price']:.2f} "
                f"| {sig['days_held']} kun | {sig['scanner']}"
            )

    send_telegram_text_to("\n".join(lines), RESULTS_CHAT_ID)
    print(f"[Kunlik hisobot] yuborildi ({len(closed)} yopilgan, {len(still_open_list)} ochiq)")


def send_monthly_tracking_report():
    """Oy oxirida umumiy statistika chiqaradi."""
    signals = load_signals_db()
    now = datetime.now()
    month_str = now.strftime("%Y-%m")

    month_signals = [s for s in signals if s["entry_date"].startswith(month_str)]
    if not month_signals:
        return

    total         = len(month_signals)
    profit_count  = sum(1 for s in month_signals if s["status"] == "profit")
    loss_count    = sum(1 for s in month_signals if s["status"] == "loss")
    expired_count = sum(1 for s in month_signals if s["status"] == "expired")
    open_count    = sum(1 for s in month_signals if s["status"] == "open")

    closed_signals = [s for s in month_signals if s["pct_change"] is not None]
    avg_pct = sum(s["pct_change"] for s in closed_signals) / len(closed_signals) if closed_signals else 0

    by_scanner = {}
    for s in month_signals:
        by_scanner.setdefault(s["scanner"], []).append(s)

    lines = [
        f"📈 <b>Oylik xulosa — {now.strftime('%B %Y')}</b>\n",
        f"Jami signallar: <b>{total}</b>",
        f"✅ Foydada yopilgan: <b>{profit_count}</b>",
        f"❌ Zararda yopilgan: <b>{loss_count}</b>",
        f"⏱ Muddati tugagan: <b>{expired_count}</b>",
        f"📊 Hali ochiq: <b>{open_count}</b>",
        f"💰 O'rtacha natija: <b>{avg_pct:+.2f}%</b>\n",
        f"📋 <b>Scanner bo'yicha taqsimot:</b>",
    ]
    for scanner, sigs in by_scanner.items():
        s_profit = sum(1 for s in sigs if s["status"] == "profit")
        lines.append(f"• {scanner}: {len(sigs)} ta signal, {s_profit} ta foydada")

    send_telegram_text_to("\n".join(lines), RESULTS_CHAT_ID)
    print(f"[Oylik hisobot] yuborildi ({total} signal)")


def check_and_send_monthly_report():
    now = datetime.now()
    last_sent = ""
    if os.path.exists(LAST_MONTHLY_REPORT_FILE):
        with open(LAST_MONTHLY_REPORT_FILE, "r") as f:
            last_sent = f.read().strip()

    current_month = now.strftime("%Y-%m")
    if now.day == 1 and last_sent != current_month:
        send_monthly_tracking_report()
        with open(LAST_MONTHLY_REPORT_FILE, "w") as f:
            f.write(current_month)


# ── Asosiy tsikl ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 TOS Signal Tracker Bot ishga tushdi!")
    print(f"   Signal kanali: {SIGNAL_CHAT_ID}")
    print(f"   Natija kanali: {RESULTS_CHAT_ID}")
    print(f"   Har {CHECK_INTERVAL}s tekshiradi...")
    print(f"   Tracking: Target +{TARGET_PCT}%, Stop {STOP_LOSS_PCT}%, Max {MAX_HOLD_DAYS} kun\n")

    last_daily_report_date = ""

    while True:
        poll_telegram_updates()

        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        if now.hour >= 22 and last_daily_report_date != today_str:
            try:
                send_daily_tracking_report()
            except Exception as e:
                print(f"[Kunlik hisobot xato] {e}")
            last_daily_report_date = today_str

        try:
            check_and_send_monthly_report()
        except Exception as e:
            print(f"[Oylik hisobot xato] {e}")

        time.sleep(CHECK_INTERVAL)
