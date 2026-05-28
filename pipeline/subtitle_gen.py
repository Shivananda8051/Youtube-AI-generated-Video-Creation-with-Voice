import whisper
import re


def _format_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_subtitles(audio_path: str, output_path: str) -> str:
    """Generate SRT subtitles from audio using Whisper with word-level timestamps.

    Creates short subtitle segments (2-4 words) suitable for YouTube Shorts style.

    Args:
        audio_path: Path to the audio file.
        output_path: Path to save the SRT file.

    Returns:
        The output SRT file path.
    """
    model = whisper.load_model("base")

    result = model.transcribe(
        audio_path,
        word_timestamps=True,
        language="en",
    )

    srt_entries = []
    counter = 1

    for segment in result["segments"]:
        words = segment.get("words", [])
        if not words:
            # Fallback: use segment-level timing
            srt_entries.append(
                f"{counter}\n"
                f"{_format_timestamp(segment['start'])} --> {_format_timestamp(segment['end'])}\n"
                f"{segment['text'].strip()}\n"
            )
            counter += 1
            continue

        # Group words into chunks of 3-4 for Shorts style
        chunk_size = 3
        for i in range(0, len(words), chunk_size):
            chunk = words[i:i + chunk_size]
            start_time = chunk[0]["start"]
            end_time = chunk[-1]["end"]
            text = " ".join(w["word"].strip() for w in chunk)

            # Clean up text
            text = re.sub(r'\s+', ' ', text).strip()
            if not text:
                continue

            srt_entries.append(
                f"{counter}\n"
                f"{_format_timestamp(start_time)} --> {_format_timestamp(end_time)}\n"
                f"{text.upper()}\n"
            )
            counter += 1

    # Write SRT file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_entries))

    return output_path
