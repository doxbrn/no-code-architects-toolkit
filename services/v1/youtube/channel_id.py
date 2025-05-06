import requests
from bs4 import BeautifulSoup
import re

def get_channel_id_from_url(youtube_url: str) -> str | None:
    """
    Fetches a YouTube page and extracts the channel ID.

    Args:
        youtube_url: The URL of the YouTube page (channel or video).

    Returns:
        The channel ID if found, otherwise None.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        )
    }
    try:
        response = requests.get(youtube_url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Attempt 1: Look for <meta itemprop="channelId" content="...">
        meta_tag = soup.find('meta', itemprop='channelId')
        if meta_tag and meta_tag.get('content'):
            return meta_tag['content']

        # Attempt 2: Look for channelId or externalId in ytInitialData
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and 'ytInitialData' in script.string:
                # Primary regex for channelId
                match_channel_id = re.search(
                    r'"channelId":"([a-zA-Z0-9_\-]+)"', 
                    script.string
                )
                if match_channel_id:
                    return match_channel_id.group(1)
                
                # Fallback for externalId
                match_external_id = re.search(
                    r'"externalId":"([a-zA-Z0-9_\-]+)"', 
                    script.string
                )
                if match_external_id:
                    return match_external_id.group(1)
                
                # Broader search within browseEndpoint for browseId (channelId)
                browse_match = re.search(
                    r'"browseEndpoint":{[^}]*"browseId":"([a-zA-Z0-9_\-]+)"'
                    , script.string)
                if browse_match:
                    return browse_match.group(1)

        # Attempt 3: Look for canonical URL pointing to the channel
        canonical_link = soup.find('link', rel='canonical')
        if canonical_link and canonical_link.get('href'):
            href = canonical_link['href']
            match_canonical = re.match(
                r'https?://www\.youtube\.com/channel/([a-zA-Z0-9_\-]+)',
                href
            )
            if match_canonical:
                return match_canonical.group(1)

        return None

    except requests.RequestException as e:
        # Log the error or handle it as per application's logging strategy
        print(f"Error fetching URL {youtube_url}: {e}")
        return None
    except Exception as e:
        # Log the error or handle it
        print(f"An error occurred while processing {youtube_url}: {e}")
        return None

if __name__ == '__main__':
    # Test cases
    test_urls = [
        "https://www.youtube.com/channel/UC_x5XG1OV2P6uZZ5FSM9Ttw", # Google Developers (Channel URL)
        "https://www.youtube.com/user/GoogleDevelopers", # Google Developers (Legacy user URL)
        "https://www.youtube.com/@GoogleDevelopers", # Google Developers (Handle URL)
        "https://www.youtube.com/watch?v=Y_2gXg_K26U", # A video from Google Developers
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ", # Rick Astley - Video URL
        "https://www.youtube.com/@LinusTechTips", # Linus Tech Tips (Handle URL)
        "https://www.youtube.com/c/LinusTechTips", # Linus Tech Tips (Legacy custom URL)
        "https://www.youtube.com/madebygoogle", # Made by Google (Vanity URL, might resolve to /@madebygoogle)
    ]
    print("Running tests...")
    for url in test_urls:
        channel_id = get_channel_id_from_url(url)
        print(f"URL: {url}\n  -> Channel ID: {channel_id}\n")

    # Expected output (channel IDs can sometimes change or YouTube might alter their page structure):
    # UC_x5XG1OV2P6uZZ5FSM9Ttw for Google Developers related URLs
    # UCUYoUwYf5nKZDJD3s_22zYQ for Linus Tech Tips related URLs
    # UC38IQsAvIsxxjztd_EJO2rQ for Rick Astley's video's channel
    # UCQ16c6dtk2cpNK2E1nOahLg for MadeByGoogle 