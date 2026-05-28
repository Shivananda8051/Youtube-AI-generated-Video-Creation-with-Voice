import subprocess
import os
import json
from config import VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS, TEMP_DIR, FFMPEG_BIN


def _get_duration(file_path: str) -> float:
    """Get duration of a media file using ffmpeg."""
    cmd = [
        FFMPEG_BIN, "-i", file_path,
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    # Parse duration from stderr (ffmpeg outputs info to stderr)
    import re
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", result.stderr)
    if match:
        h, m, s, cs = match.groups()
        return int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100
    raise ValueError(f"Could not determine duration of {file_path}")


def _prepare_clip(clip_path: str, index: int, duration: float) -> str:
    """Resize/crop a clip to 1080x1920 and trim to specified duration."""
    output = os.path.join(str(TEMP_DIR), f"prepared_{index}.mp4")

    cmd = [
        FFMPEG_BIN, "-y",
        "-i", clip_path,
        "-t", str(duration),
        "-vf", (
            f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
            f"fps={VIDEO_FPS}"
        ),
        "-an",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        output,
    ]

    subprocess.run(cmd, capture_output=True, text=True, check=True)
    return output


def assemble_video(
    clips: list,
    audio_path: str,
    subtitle_path: str,
    output_path: str,
    bg_music_path: str | None = None,
) -> str:
    """Assemble final 28-30s video from 4 clips, narration audio, subtitles, and optional background music.

    Structure: Hook (first clip ~6s) + 3 content clips (~7s each) = ~28-30s total
    """
    audio_duration = _get_duration(audio_path)

    clip_count = len(clips)
    if clip_count == 0:
        raise ValueError("No clips provided for video assembly")

    # Split duration: first clip gets ~6s for hook, rest split evenly
    if clip_count >= 2:
        hook_duration = min(6.0, audio_duration * 0.2)
        remaining = audio_duration - hook_duration
        body_duration = remaining / (clip_count - 1)
    else:
        hook_duration = audio_duration
        body_duration = 0

    # Prepare each clip (resize/crop/trim)
    prepared_clips = []
    for i, clip in enumerate(clips):
        dur = hook_duration if i == 0 else body_duration
        try:
            prepared = _prepare_clip(clip, i, dur)
            prepared_clips.append(prepared)
        except subprocess.CalledProcessError:
            continue

    if not prepared_clips:
        raise ValueError("Failed to prepare any clips")

    # Create concat file
    concat_file = os.path.join(str(TEMP_DIR), "concat_list.txt")
    with open(concat_file, "w") as f:
        for clip in prepared_clips:
            clip_path = clip.replace("\\", "/")
            f.write(f"file '{clip_path}'\n")

    # Concatenate clips
    concat_output = os.path.join(str(TEMP_DIR), "concatenated.mp4")
    cmd_concat = [
        FFMPEG_BIN, "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        concat_output,
    ]
    subprocess.run(cmd_concat, capture_output=True, text=True, check=True)

    # Step 1: Burn subtitles into video (separate step to avoid filter conflicts)
    # Copy SRT to a simple filename next to concat output to avoid Windows path escaping issues
    import shutil
    simple_srt = os.path.join(str(TEMP_DIR), "subs.srt")
    shutil.copy2(subtitle_path, simple_srt)

    subtitle_style = (
        "FontName=Arial,FontSize=14,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BorderStyle=3,Outline=2,"
        "Shadow=0,Alignment=2,MarginV=80"
    )

    subtitled_output = os.path.join(str(TEMP_DIR), "subtitled.mp4")

    # Use -sub_input flag approach to avoid subtitle filter path escaping on Windows
    cmd_subs = [
        FFMPEG_BIN, "-y",
        "-i", concat_output,
        "-vf", f"subtitles=subs.srt:force_style='{subtitle_style}'",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-an",
        subtitled_output,
    ]
    # Run from TEMP_DIR so relative path "subs.srt" works
    subprocess.run(cmd_subs, capture_output=True, text=True, check=True, cwd=str(TEMP_DIR))

    # Step 2: Mix audio and mux with video
    has_music = bg_music_path and os.path.exists(bg_music_path)

    if has_music:
        # Mix narration (full volume) + background music (15% volume)
        cmd_final = [
            FFMPEG_BIN, "-y",
            "-i", subtitled_output,
            "-i", audio_path,
            "-i", bg_music_path,
            "-filter_complex",
            f"[1:a]volume=1.0[narration];"
            f"[2:a]atrim=0:{audio_duration},volume=0.15[music];"
            f"[narration][music]amix=inputs=2:duration=first:dropout_transition=2[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            output_path,
        ]
    else:
        # Narration only
        cmd_final = [
            FFMPEG_BIN, "-y",
            "-i", subtitled_output,
            "-i", audio_path,
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            output_path,
        ]

    subprocess.run(cmd_final, capture_output=True, text=True, check=True)

    # Cleanup
    for f in prepared_clips + [concat_file, concat_output, subtitled_output, simple_srt]:
        try:
            os.remove(f)
        except OSError:
            pass

    return output_path
