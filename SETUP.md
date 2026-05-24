# Setup Guide — Facebook Automation Pipeline

## Step 1 — Install Dependencies

```bash
cd facebook-automation
pip install -r requirements.txt
brew install ffmpeg        # macOS
# OR: sudo apt install ffmpeg   (Linux)
```

## Step 2 — Get Your API Keys

| Service | Where to get it | Cost |
|---|---|---|
| **Anthropic (Claude)** | console.anthropic.com | ~$5 free credit |
| **ElevenLabs** | elevenlabs.io | Free tier (10k chars/mo) |
| **Pexels** | pexels.com/api | Free |
| **Facebook Graph API** | developers.facebook.com | Free |
| **Reddit** | reddit.com/prefs/apps | Free |

## Step 3 — Configure Environment

```bash
cp .env.example .env
# Open .env and fill in all API keys
```

## Step 4 — Get Facebook Page Access Token

1. Go to developers.facebook.com
2. Create an App → Business type
3. Add "Pages" product
4. Generate a Page Access Token for your page
5. Paste into .env as FB_ACCESS_TOKEN
6. Paste your Page ID as FB_PAGE_ID

## Step 5 — Test Each Module

```bash
# Test trend finder (no API key needed)
python modules/trend_finder.py

# Test script writer (needs ANTHROPIC_API_KEY)
python modules/script_writer.py

# Test voiceover (needs ELEVENLABS_API_KEY)
python modules/voiceover.py

# Test thumbnail (needs PEXELS_API_KEY)
python modules/thumbnail.py
```

## Step 6 — Run Full Pipeline

```bash
# Dry run (no Facebook publish)
python main.py --dry-run

# Full run with auto topic
python main.py

# Full run with custom topic
python main.py --topic "Why Python is the best language in 2025"

# Check analytics
python main.py --analytics
```

## Step 7 — Start the Scheduler (Daily Automation)

```bash
# Run once now, then schedule daily
python scheduler.py --now

# Schedule only (no immediate run)
python scheduler.py
```

## Project Structure

```
facebook-automation/
├── main.py              ← Run this for full pipeline
├── scheduler.py         ← Run this for daily automation
├── config.py            ← Settings loaded from .env
├── requirements.txt
├── .env                 ← Your API keys (never commit this)
├── modules/
│   ├── trend_finder.py  ← Google Trends + Reddit
│   ├── script_writer.py ← Claude API script generation
│   ├── voiceover.py     ← ElevenLabs text-to-speech
│   ├── video_builder.py ← MoviePy + FFmpeg video assembly
│   ├── thumbnail.py     ← Pillow thumbnail creation
│   ├── publisher.py     ← Facebook Graph API uploader
│   └── analytics.py     ← Facebook Insights tracker
├── output/
│   ├── scripts/         ← Generated JSON scripts
│   ├── audio/           ← Generated MP3 files
│   ├── videos/          ← Final MP4 files
│   └── thumbnails/      ← Generated JPG thumbnails
└── database/
    └── posts.db         ← SQLite tracking database
```
