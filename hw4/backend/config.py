"""Application settings, loaded from the repo-root .env."""

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

# config.py -> backend -> hw4 -> MGT409 (repo root holds the shared .env)
BACKEND_DIR = Path(__file__).resolve().parent
HW_DIR = BACKEND_DIR.parent
PROJECT_ROOT = HW_DIR.parent

# Prefer hw4/.env (what .env.example tells you to create), and fall back to the
# repository-root .env so a shared key still works when hw4 sits inside a larger
# coursework repo. The first file to define a variable wins.
load_dotenv(HW_DIR / ".env")
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = HW_DIR / "data"
DB_PATH = DATA_DIR / "campus_customs.db"
PRODUCT_IMAGE_DIR = DATA_DIR / "products"
#: Short product loops, built by scripts/make_motion_loops.py. Optional — the site
#: works unchanged when the directory is empty.
MOTION_DIR = DATA_DIR / "motion"

#: Append-only record of agent activity. Lives in output/ because it is a
#: deliverable to be read, not application state.
AUDIT_PATH = HW_DIR / "output" / "audit_trail.json"

# Portkey fronts the OpenAI-compatible endpoint; the key never lives in source.
PORTKEY_API_KEY = os.environ.get("PORTKEY_API_KEY", "")
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
MODEL_ID = "gpt-5.6-luna"

# Signs session tokens. Set JWT_SECRET in .env to keep sessions across restarts;
# without it a random secret is generated per process, which is safe (nobody can
# forge a token) but logs everyone out on restart. Never fall back to a fixed
# string — a known secret lets anyone mint a session for any user id.
JWT_SECRET = os.environ.get("JWT_SECRET") or secrets.token_urlsafe(48)
JWT_ALGORITHM = "HS256"
JWT_TTL_HOURS = 24

CORS_ORIGINS = ["http://localhost:5190", "http://127.0.0.1:5190"]

# Where password-reset links point. The frontend owns the /reset-password page.
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5190")
