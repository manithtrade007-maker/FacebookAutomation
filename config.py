import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ────────────────────────────────────────────
GEMINI_API_KEY      = os.getenv("GEMINI_API_KEY")       # free at aistudio.google.com
# Edge-TTS needs no API key — completely free
ANTHROPIC_API_KEY   = os.getenv("ANTHROPIC_API_KEY")    # optional paid upgrade
ELEVENLABS_API_KEY  = os.getenv("ELEVENLABS_API_KEY")   # optional paid upgrade
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
FB_PAGE_ID          = os.getenv("FB_PAGE_ID")
FB_ACCESS_TOKEN     = os.getenv("FB_ACCESS_TOKEN")
REDDIT_CLIENT_ID    = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET= os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT   = os.getenv("REDDIT_USER_AGENT", "FacebookBot/1.0")
PEXELS_API_KEY      = os.getenv("PEXELS_API_KEY")

# ── Content Settings ────────────────────────────────────
NICHE              = os.getenv("NICHE", "tech")
TARGET_AUDIENCE    = os.getenv("TARGET_AUDIENCE", "US")
VIDEOS_PER_DAY     = int(os.getenv("VIDEOS_PER_DAY", 1))
POST_TIME          = os.getenv("POST_TIME", "18:00")

# ── Paths ───────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
OUTPUT_SCRIPTS  = os.path.join(BASE_DIR, "output", "scripts")
OUTPUT_AUDIO    = os.path.join(BASE_DIR, "output", "audio")
OUTPUT_VIDEOS   = os.path.join(BASE_DIR, "output", "videos")
OUTPUT_THUMBS   = os.path.join(BASE_DIR, "output", "thumbnails")
ASSETS_DIR      = os.path.join(BASE_DIR, "assets")
DB_PATH         = os.path.join(BASE_DIR, "database", "posts.db")

# ── Video Settings ──────────────────────────────────────
VIDEO_WIDTH     = 1280
VIDEO_HEIGHT    = 720
VIDEO_FPS       = 24
MIN_DURATION    = 180   # 3 minutes minimum for monetization

# ── Niche → Subreddits & Google Trends keywords ─────────
NICHE_CONFIG = {
    "tech": {
        "subreddits": ["technology", "programming", "artificial", "MachineLearning", "Python"],
        "trend_keywords": ["technology", "artificial intelligence", "coding", "software"],
        "script_tone": "educational and engaging, like a knowledgeable friend explaining tech",
    },
    "finance": {
        "subreddits": ["personalfinance", "investing", "CryptoCurrency", "stocks"],
        "trend_keywords": ["investing", "crypto", "stock market", "personal finance"],
        "script_tone": "clear and practical, like a financial advisor talking to a friend",
    },
    "ai": {
        "subreddits": ["artificial", "MachineLearning", "ChatGPT", "OpenAI"],
        "trend_keywords": ["ChatGPT", "AI tools", "artificial intelligence", "machine learning"],
        "script_tone": "excited and accessible, making complex AI topics easy to understand",
    },
}
