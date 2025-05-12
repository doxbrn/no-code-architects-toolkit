# Endpoint: POST /v1/video/pexels_montage

## Overview

Creates a video montage by searching Pexels for videos matching a specific term, downloading a specified number of clips, and concatenating them with basic effects (fade transitions, color adjustment).

## Request

### Headers

- `Authorization`: `Bearer <YOUR_API_KEY>` (If authentication is enabled)
- `Content-Type`: `application/json`

### Body

The request body should be a JSON object with the following fields:

```json
{
  "pexels_term": "string (required)",
  "n_videos": "integer (required, > 0)",
  "target_width": "integer (optional, default: 1920)",
  "target_height": "integer (optional, default: 1080)"
}
```

- `pexels_term`: The search term used to find videos on Pexels.
- `n_videos`: The desired number of video clips to include in the final montage.
- `target_width`: The desired width (in pixels) for the output video. Defaults to 1920.
- `target_height`: The desired height (in pixels) for the output video. Defaults to 1080.

### Example cURL Request

```bash
curl -X POST "http://<your_server>/v1/video/pexels_montage" \
     -H "Authorization: Bearer <YOUR_API_KEY>" \
     -H "Content-Type: application/json" \
     -d '{
           "pexels_term": "futuristic technology",
           "n_videos": 5,
           "target_width": 1280,
           "target_height": 720
         }'
```

## Response

### Success (200 OK)

- **Body**: The generated montage video file (`video/mp4`).

### Errors

- **400 Bad Request**: Invalid JSON payload or parameters (e.g., `n_videos` <= 0).
- **401 Unauthorized**: Invalid or missing API key.
- **500 Internal Server Error**: Processing error (e.g., Pexels API key missing/invalid, failure during video download or processing, unable to find enough Pexels videos).

## Notes

- The service attempts to find unique video combinations for repeated requests with the same term, but this depends on Pexels providing enough distinct videos.
- Processing time depends on the number and duration of videos being fetched and processed.
- Ensure the PEXELS_API_KEY environment variable is correctly configured on the server. 