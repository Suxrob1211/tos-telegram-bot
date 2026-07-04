import os
import urllib.parse
import requests

SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/137.0 Safari/537.36"
    ),
    "Referer": "https://finviz.com/",
    "Accept": "image/png,image/*,*/*",
}


def get_chart(ticker: str):

    ticker = ticker.upper()

    finviz = (
        f"https://charts2.finviz.com/chart.ashx?"
        f"t={ticker}&ty=c&ta=1&p=d&s=l"
    )

    urls = [
        finviz,
    ]

    if SCRAPERAPI_KEY:
        urls.append(
            "https://api.scraperapi.com/"
            f"?api_key={SCRAPERAPI_KEY}"
            f"&url={urllib.parse.quote(finviz,safe='')}"
            "&render=false"
        )

    for url in urls:

        try:

            r = requests.get(
                url,
                headers=HEADERS,
                timeout=20,
            )

            if r.status_code != 200:
                print(f"[Chart] HTTP {r.status_code}")
                continue

            if r.content[:8] != b"\x89PNG\r\n\x1a\n":
                print("[Chart] PNG emas")
                continue

            print(f"[Chart] Finviz OK ({len(r.content)//1024}KB)")
            return r.content

        except Exception as e:

            print(f"[Chart] {e}")

    return None
