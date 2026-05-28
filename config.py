import os
from pathlib import Path
from dotenv import load_dotenv
import imageio_ffmpeg

load_dotenv()

# FFmpeg binary path (from imageio-ffmpeg package)
FFMPEG_BIN = imageio_ffmpeg.get_ffmpeg_exe()

# Add ffmpeg directory to PATH so Whisper and other tools can find it
_ffmpeg_dir = os.path.dirname(FFMPEG_BIN)
# Also create a symlink/copy named "ffmpeg.exe" if the binary has a long name
_ffmpeg_shortname = os.path.join(_ffmpeg_dir, "ffmpeg.exe")
if not os.path.exists(_ffmpeg_shortname):
    import shutil
    shutil.copy2(FFMPEG_BIN, _ffmpeg_shortname)
os.environ["PATH"] = _ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

# Paths
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR = BASE_DIR / "temp"
CREDENTIALS_DIR = BASE_DIR / "credentials"
STATIC_DIR = BASE_DIR / "static"
ASSETS_DIR = BASE_DIR / "assets"

# Ensure dirs exist
OUTPUT_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)
CREDENTIALS_DIR.mkdir(exist_ok=True)

# ElevenLabs
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "IRHApOXLvnW57QJPQH2P")

# Pexels
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

# Ollama
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "kimi")

# YouTube OAuth
YOUTUBE_CLIENT_SECRET_FILE = CREDENTIALS_DIR / "client_secret.json"
YOUTUBE_TOKEN_FILE = CREDENTIALS_DIR / "youtube_token.json"
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
YOUTUBE_REDIRECT_URI = "http://localhost:8000/api/yt-callback"

# Video
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30

# Default hashtags
DEFAULT_HASHTAGS = ["#Shorts", "#animalfacts"]

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
