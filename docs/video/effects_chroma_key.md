# Endpoint: POST /v1/video/chroma_key

## Overview

Applies a chroma key effect to an uploaded video. It replaces the specified chroma key color (e.g., green screen) in the foreground video with background footage fetched from Pexels based on a search term.

## Request

### Headers

- `Authorization`: `Bearer <YOUR_API_KEY>` (If authentication is enabled)

### Body

This endpoint uses `multipart/form-data` for the request body.

- **`input_video`** (`file`, required): The video file containing the foreground subject against a chroma key background.
- **`payload`** (`json`, required): A JSON object containing the parameters for the chroma key effect. This should be sent as a separate part in the multipart request.

**JSON Payload Fields:**

```json
{
  "pexels_term": "string (required)",
  "chroma_color": "string (optional, default: #32CD32)",
  "transition": "float (optional, default: 1.5)",
  "effect": "string (optional, default: fade)"
}
```

- `pexels_term`: The search term used to find background videos on Pexels.
- `chroma_color`: The hex color code of the background to remove (e.g., "#00FF00" for green, "#0000FF" for blue). Defaults to lime green ("#32CD32").
- `transition`: The duration (in seconds) of the crossfade transition between background clips (if the `fade` effect is used). Defaults to 1.5 seconds.
- `effect`: The visual effect applied to the background clips. Currently supports "fade" (adds fade-in/out transitions) and "contrast" (increases contrast slightly). Defaults to "fade".

### Example cURL Request

```bash
curl -X POST "http://<your_server>/v1/video/chroma_key" \
     -H "Authorization: Bearer <YOUR_API_KEY>" \
     -F "input_video=@/path/to/your/greenscreen_video.mp4" \
     -F "payload={\"pexels_term\": \"nature landscape\", \"chroma_color\": \"#00FF00\"};type=application/json"
```

## Response

### Success (200 OK)

- **Body**: The processed video file (`video/mp4`).

### Errors

- **400 Bad Request**: Invalid input (e.g., missing file, invalid JSON payload).
- **401 Unauthorized**: Invalid or missing API key.
- **500 Internal Server Error**: Processing error (e.g., Pexels API key missing/invalid, failure during video processing, unable to find suitable Pexels videos).

## Notes

- Processing time depends on the duration and resolution of the input video and the fetched background clips.
- Ensure the PEXELS_API_KEY environment variable is correctly configured on the server.
- The quality of the chroma key effect heavily depends on the quality of the input video's green screen (even lighting, no shadows, distinct color). 