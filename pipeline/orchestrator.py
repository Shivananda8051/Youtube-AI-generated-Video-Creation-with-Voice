import os
import uuid
import shutil
import traceback
from datetime import datetime
from config import OUTPUT_DIR, TEMP_DIR

from pipeline.script_gen import generate_script_and_metadata
from pipeline.voice_gen import generate_voice
from pipeline.subtitle_gen import generate_subtitles
from pipeline.stock_footage import download_clips
from pipeline.video_assembly import assemble_video
from pipeline.youtube_upload import upload_video, is_authenticated

# In-memory job tracking
jobs: dict = {}

# Store uploaded music files per job
uploaded_music: dict = {}


def _update_job(job_id: str, step: str, status: str, **extras):
    """Update job progress."""
    if job_id not in jobs:
        return
    jobs[job_id]["current_step"] = step
    jobs[job_id]["steps"][step] = status
    jobs[job_id].update(extras)


def run_pipeline(job_id: str, topic: str):
    """Run the full video generation pipeline.

    Args:
        job_id: Unique job identifier for tracking progress.
        topic: The video topic provided by the user.
    """
    # Initialize job
    jobs[job_id] = {
        "id": job_id,
        "topic": topic,
        "status": "running",
        "current_step": "script_generation",
        "steps": {
            "script_generation": "pending",
            "metadata_generation": "pending",
            "voice_generation": "pending",
            "subtitle_generation": "pending",
            "stock_footage": "pending",
            "video_assembly": "pending",
            "youtube_upload": "pending",
        },
        "video_path": None,
        "youtube_url": None,
        "error": None,
        "created_at": datetime.now().isoformat(),
    }

    # Create job-specific temp directory
    job_temp = os.path.join(str(TEMP_DIR), job_id)
    os.makedirs(job_temp, exist_ok=True)

    try:
        # Step 1+2: Generate script + metadata together (sections with matching keywords)
        _update_job(job_id, "script_generation", "running")
        result = generate_script_and_metadata(topic)
        script = result["script"]
        _update_job(job_id, "script_generation", "completed")

        _update_job(job_id, "metadata_generation", "running")
        metadata = result  # title, description, hashtags, keywords, sections all in one
        _update_job(job_id, "metadata_generation", "completed")

        # Step 3: Generate voice from full script
        _update_job(job_id, "voice_generation", "running")
        audio_path = os.path.join(job_temp, "narration.mp3")
        generate_voice(script, audio_path)
        _update_job(job_id, "voice_generation", "completed")

        # Step 4: Generate subtitles
        _update_job(job_id, "subtitle_generation", "running")
        subtitle_path = os.path.join(job_temp, "subtitles.srt")
        generate_subtitles(audio_path, subtitle_path)
        _update_job(job_id, "subtitle_generation", "completed")

        # Step 5: Download stock footage (1 clip per section keyword, in order)
        _update_job(job_id, "stock_footage", "running")
        keywords = metadata.get("keywords", topic.split()[:4])
        clips = download_clips(keywords, count=4, output_dir=job_temp)
        if not clips:
            raise ValueError("Failed to download any stock footage clips")
        _update_job(job_id, "stock_footage", "completed")

        # Step 6: Assemble video
        _update_job(job_id, "video_assembly", "running")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"short_{timestamp}_{job_id[:8]}.mp4"
        output_path = os.path.join(str(OUTPUT_DIR), output_filename)

        # Check if user uploaded background music for this job
        music_path = uploaded_music.get(job_id)

        assemble_video(
            clips=clips,
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            output_path=output_path,
            bg_music_path=music_path,
        )
        _update_job(job_id, "video_assembly", "completed", video_path=output_filename)

        # Step 7: Upload to YouTube (only if authenticated)
        _update_job(job_id, "youtube_upload", "running")
        if is_authenticated():
            title = metadata.get("title", topic)
            description = metadata.get("description", f"Video about {topic}")
            hashtags = metadata.get("hashtags", ["#Shorts"])
            youtube_url = upload_video(output_path, title, description, hashtags)
            _update_job(job_id, "youtube_upload", "completed", youtube_url=youtube_url)
        else:
            _update_job(job_id, "youtube_upload", "skipped")

        # Done
        jobs[job_id]["status"] = "completed"

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        print(f"Pipeline error for job {job_id}: {error_msg}")
        traceback.print_exc()
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = error_msg

        # Mark remaining steps as failed
        for step, status in jobs[job_id]["steps"].items():
            if status in ("pending", "running"):
                jobs[job_id]["steps"][step] = "failed"

    finally:
        # Cleanup temp files (but not the music — it may be reused)
        try:
            shutil.rmtree(job_temp, ignore_errors=True)
        except Exception:
            pass
        # Clean up music reference
        uploaded_music.pop(job_id, None)


def get_job_status(job_id: str) -> dict | None:
    """Get the current status of a job."""
    return jobs.get(job_id)
