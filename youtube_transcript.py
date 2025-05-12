import requests
import json
import re
from urllib.parse import parse_qs, urlparse, quote
import html

# Airtable Configuration - Using direct values
# Use a simpler access token format (this is generated from MCP authentication)
AIRTABLE_API_KEY = "pat6cng1onAU7aEVv.a0e52b2cf7452048e02537a41f4571d541b0419bd523fc99faa5b72f2eb52132"  # Updated API key
AIRTABLE_BASE_ID = "appVgvW0XEsJLXZ0P"
AIRTABLE_TABLE_NAME = "🕵️ VideosREF"

# URL-encode the table name to handle special characters
ENCODED_TABLE_NAME = quote(AIRTABLE_TABLE_NAME)

AIRTABLE_API_URL = (
    f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{ENCODED_TABLE_NAME}"
)

HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json",
}


def extract_video_id(url):
    """Extract the video ID from a YouTube URL."""
    if not url:  # Added check for empty URL
        return None
    parsed_url = urlparse(url)
    if parsed_url.netloc == 'youtu.be':
        return parsed_url.path[1:]
    if parsed_url.netloc in ('www.youtube.com', 'youtube.com'):
        if parsed_url.path == '/watch':
            query = parse_qs(parsed_url.query)
            return query.get('v', [None])[0]  # Made .get more robust
        if parsed_url.path.startswith('/embed/'):
            return parsed_url.path.split('/')[2]
        if parsed_url.path.startswith('/v/'):
            return parsed_url.path.split('/')[2]
    return None


def get_youtube_transcript(url):  # Removed unused text_only parameter
    """Get transcript from a YouTube video."""
    video_id = extract_video_id(url)
    if not video_id:
        return {"error": "Invalid YouTube URL or no Video ID found"}

    try:  # Added try-except for robustness
        video_page_url = f"https://www.youtube.com/watch?v={video_id}"
        response = requests.get(video_page_url)
        # Raise HTTPError for bad responses (4xx or 5xx)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to access video. Error: {e}"}

    html_content = response.text
    pattern = r'ytInitialPlayerResponse\s*=\s*({.+?});'
    match = re.search(pattern, html_content)

    if not match:
        return {"error": "Could not find transcript data in the video page"}

    try:
        player_response = json.loads(match.group(1))
        captions_data = player_response['captions']
        renderer = captions_data['playerCaptionsTracklistRenderer']
        caption_tracks = renderer['captionTracks']

        if not caption_tracks:  # Simplified check
            return {"error": "No caption tracks found for this video"}

        default_track = next(
            (t for t in caption_tracks if t.get('isDefault')),
            caption_tracks[0]
        )
        
        base_url = default_track['baseUrl']
        language_info = default_track.get('name', {})
        language = language_info.get('simpleText', 'Unknown')
        transcript_url = f"{base_url}&fmt=json3"

        transcript_response = requests.get(transcript_url)
        transcript_response.raise_for_status()
        transcript_data = transcript_response.json()
        
        full_text_segments = []
        for event in transcript_data.get('events', []):
            if 'segs' in event:
                text_segments = [
                    html.unescape(seg['utf8']).strip()
                    for seg in event['segs'] if 'utf8' in seg
                ]
                if text_segments:
                    full_text_segments.append(' '.join(text_segments))
        
        # Ensure no empty strings joined
        full_text = ' '.join(filter(None, full_text_segments))
        
        return {
            "success": True,
            "video_id": video_id,
            "language": language,
            "full_text": full_text
        }
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
        return {"error": f"Error processing transcript data: {e}"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to fetch transcript content. Error: {e}"}


def get_airtable_records():
    """Fetches records from Airtable, prioritizing by View_Count."""
    all_records = []
    params = {"sort[0][field]": "View_Count", "sort[0][direction]": "desc"}
    current_offset = None

    while True:
        if current_offset:
            params["offset"] = current_offset
        
        try:
            print(f"Making request to: {AIRTABLE_API_URL}")
            print(f"With headers: {HEADERS}")
            
            response = requests.get(
                AIRTABLE_API_URL, headers=HEADERS, params=params
            )
            print(f"Response status: {response.status_code}")
            # Print first 200 chars of response only
            print(f"Response content: {response.text[:200]}...")
            
            response.raise_for_status()
            data = response.json()
            all_records.extend(data.get("records", []))
            current_offset = data.get("offset")
            if not current_offset:
                break
        except requests.exceptions.RequestException as e:
            print(f"Error fetching Airtable records: {e}")
            return None
        except json.JSONDecodeError:
            print(f"Error decoding Airtable JSON response: {response.text}")
            return None
            
    return all_records


def update_airtable_record(record_id, transcript_text):
    """Updates an Airtable record with the transcript."""
    payload = {"fields": {"transcript": transcript_text}}
    try:
        record_url = f"{AIRTABLE_API_URL}/{record_id}"
        response = requests.patch(record_url, headers=HEADERS, json=payload)
        response.raise_for_status()
        print(f"Successfully updated record {record_id} in Airtable.")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error updating Airtable record {record_id}: {e}")
        print(f"Response content: {response.content}")
        return None
    except json.JSONDecodeError:
        print(
            f"Error decoding Airtable JSON response for update: "
            f"{response.text}"
        )
        return None


def main():
    print("Fetching records from Airtable...")
    videos_to_process = get_airtable_records()

    if not videos_to_process:
        print("No videos found in Airtable or error fetching them.")
        return

    print(f"Found {len(videos_to_process)} videos to process.")

    for record in videos_to_process:
        record_id = record.get("id")
        fields = record.get("fields", {})
        
        # Priorizar o campo de fórmula 'Calculation' para a URL do vídeo
        video_url = fields.get("Calculation") 
        if not video_url:
            # Fallback se 'Calculation' não existir ou estiver vazio.
            # Tentar "Video URL" como alternativa.
            video_url = fields.get("Video URL")  # Nome exato.
        if not video_url:
            # Fallback final para "Video_URL" como estava antes.
            video_url = fields.get("Video_URL")

        existing_transcript = fields.get("transcript")

        if not video_url:
            print(f"Skipping record {record_id}: No Video_URL field found.")
            continue
        
        # Optional: skip if transcript already exists
        if existing_transcript:
            print(
                f"Skipping record {record_id} ({video_url}): "
                "Transcript already exists."
            )
            continue

        print(f"Processing video: {video_url} (Record ID: {record_id})")
        transcript_result = get_youtube_transcript(video_url)

        if transcript_result.get("success"):
            transcript_text = transcript_result["full_text"]
            lang = transcript_result['language']
            print(
                f"  Successfully fetched transcript ({lang}). "
                f"Length: {len(transcript_text)}"
            )
            if transcript_text:
                update_airtable_record(record_id, transcript_text)
            else:
                print(
                    f"  Transcript is empty for {video_url}. "
                    "Skipping Airtable update."
                )
        else:
            error_message = transcript_result.get("error", "Unknown error")
            print(
                f"  Error fetching transcript for {video_url}: {error_message}"
            )
            # Optionally, update Airtable with the error message
            # update_airtable_record(record_id, f"Error: {error_message}")

    print("\nProcessing complete.")


if __name__ == "__main__":
    main() 