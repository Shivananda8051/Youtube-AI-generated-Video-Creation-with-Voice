import uuid
import threading
import os
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from config import HOST, PORT, OUTPUT_DIR, STATIC_DIR, TEMP_DIR, YOUTUBE_CLIENT_SECRET_FILE
from pipeline.orchestrator import run_pipeline, get_job_status, uploaded_music
from pipeline.youtube_upload import get_auth_url, handle_oauth_callback, is_authenticated

app = FastAPI(title="Auto YouTube Shorts Generator")

# Serve output files for download
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main UI."""
    html_path = os.path.join(str(STATIC_DIR), "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# ──────────── YouTube OAuth ────────────

@app.get("/api/yt-status")
async def yt_status():
    """Check if YouTube account is connected."""
    client_secret_exists = os.path.exists(YOUTUBE_CLIENT_SECRET_FILE)
    authenticated = is_authenticated()
    return {
        "connected": authenticated,
        "client_secret_exists": client_secret_exists,
    }


@app.get("/api/yt-auth")
async def yt_auth():
    """Redirect to Google OAuth consent screen."""
    if not os.path.exists(YOUTUBE_CLIENT_SECRET_FILE):
        return JSONResponse(
            status_code=400,
            content={
                "error": "client_secret.json not found. Please place your Google OAuth "
                         "client_secret.json file in the credentials/ folder."
            },
        )
    auth_url = get_auth_url()
    return RedirectResponse(url=auth_url)


@app.get("/api/yt-callback")
async def yt_callback(request: Request):
    """Handle Google OAuth callback."""
    code = request.query_params.get("code")
    if not code:
        return HTMLResponse(
            content="<h2>Error: No authorization code received.</h2>",
            status_code=400,
        )

    success = handle_oauth_callback(code)
    if success:
        return HTMLResponse(content="""
        <html><body style="font-family:sans-serif;text-align:center;padding-top:100px;background:#0f172a;color:white">
            <h1 style="color:#22c55e">YouTube Connected Successfully!</h1>
            <p>You can close this tab and return to the app.</p>
            <script>setTimeout(()=>window.close(), 3000)</script>
        </body></html>
        """)
    else:
        return HTMLResponse(
            content="<h2>Error: Failed to authenticate with YouTube.</h2>",
            status_code=500,
        )


# ──────────── Pipeline ────────────

@app.post("/api/generate")
async def generate(
    topic: str = Form(...),
    music: UploadFile | None = File(None),
):
    """Start the video generation pipeline with optional background music."""
    topic = topic.strip()
    if not topic:
        return JSONResponse(
            status_code=400,
            content={"error": "Topic is required."},
        )

    job_id = str(uuid.uuid4())

    # Save uploaded music if provided
    if music and music.filename:
        music_dir = os.path.join(str(TEMP_DIR), "music")
        os.makedirs(music_dir, exist_ok=True)
        music_path = os.path.join(music_dir, f"{job_id}_{music.filename}")
        content = await music.read()
        with open(music_path, "wb") as f:
            f.write(content)
        uploaded_music[job_id] = music_path

    # Run pipeline in a background thread
    thread = threading.Thread(target=run_pipeline, args=(job_id, topic), daemon=True)
    thread.start()

    return {"job_id": job_id, "status": "started"}


@app.get("/api/status/{job_id}")
async def status(job_id: str):
    """Get pipeline progress for a job."""
    job = get_job_status(job_id)
    if not job:
        return JSONResponse(
            status_code=404,
            content={"error": "Job not found."},
        )
    return job


@app.get("/api/download/{job_id}")
async def download(job_id: str):
    """Download the generated video."""
    job = get_job_status(job_id)
    if not job or not job.get("video_path"):
        return JSONResponse(
            status_code=404,
            content={"error": "Video not found."},
        )

    video_path = os.path.join(str(OUTPUT_DIR), job["video_path"])
    if not os.path.exists(video_path):
        return JSONResponse(
            status_code=404,
            content={"error": "Video file not found on disk."},
        )

    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=job["video_path"],
    )


if __name__ == "__main__":
    import uvicorn
    print(f"\n  Auto YT Pipeline running at http://localhost:{PORT}\n")
    uvicorn.run(app, host=HOST, port=PORT)
