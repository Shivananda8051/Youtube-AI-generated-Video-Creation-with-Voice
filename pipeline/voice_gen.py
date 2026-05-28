import asyncio
import edge_tts

# Good voices for YouTube Shorts narration:
# en-US-ChristopherNeural - deep male voice (great for facts/hooks)
# en-US-GuyNeural - casual male voice
# en-US-JennyNeural - friendly female voice
# en-US-AriaNeural - expressive female voice
DEFAULT_VOICE = "en-US-ChristopherNeural"


async def _generate_voice_async(script: str, output_path: str, voice: str) -> str:
    """Generate speech audio using Edge TTS (free Microsoft TTS)."""
    communicate = edge_tts.Communicate(script, voice, rate="+5%", pitch="+0Hz")
    await communicate.save(output_path)
    return output_path


def generate_voice(script: str, output_path: str, voice: str = DEFAULT_VOICE) -> str:
    """Generate speech audio from script using Edge TTS.

    Args:
        script: The narration text to convert to speech.
        output_path: Path to save the output MP3 file.
        voice: Edge TTS voice name.

    Returns:
        The output file path.
    """
    # Run async function in sync context
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're inside an async context (FastAPI), create a new loop in thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    _generate_voice_async(script, output_path, voice)
                )
                return future.result()
        else:
            return loop.run_until_complete(
                _generate_voice_async(script, output_path, voice)
            )
    except RuntimeError:
        return asyncio.run(_generate_voice_async(script, output_path, voice))
