import requests
from bs4 import BeautifulSoup
import re
from typing import Optional

def get_channel_id_from_url(youtube_url: str) -> Optional[str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        )
    }
    try:
        # Follow redirects to catch handle -> channel redirects
        resp = requests.get(youtube_url, headers=headers, timeout=10, allow_redirects=True)
        resp.raise_for_status()
        final_url = resp.url
        m = re.match(r".*?/channel/([A-Za-z0-9_\-]+)", final_url)
        if m:
            return m.group(1)

        soup = BeautifulSoup(resp.content, "html.parser")

        # 1) meta og:url fallback
        og = soup.find("meta", property="og:url")
        if og and "/channel/" in og.get("content", ""):
            return og["content"].split("/channel/")[-1]

        # 2) aggregate all JS for a broader regex search
        all_js = "".join(script.string or "" for script in soup.find_all("script"))
        match = re.search(r'"channelId":"(UC[0-9A-Za-z_\-]{22,})"', all_js)
        if match:
            return match.group(1)

        # 3) canonical link (official channel pages)
        can = soup.find("link", rel="canonical")
        if can and "/channel/" in can.get("href", ""):
            return can["href"].split("/channel/")[-1]

        return None

    except requests.RequestException as e:
        print(f"HTTP error fetching {youtube_url}: {e}")
        return None
    except Exception as e:
        print(f"Parsing error for {youtube_url}: {e}")
        return None