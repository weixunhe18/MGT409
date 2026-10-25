"""Paths, .env loading, dataset/policy loading, and runtime configuration.

Course rule (MGT 409): look for .env in the project folder first, then one level above
(staff keep a shared .env in the folder that holds every submission). This app sits two folders deep in the course
repo, so the repo root and the folder above the repo are checked too.
"""

from __future__ import annotations

import base64
import copy
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
STATIC_DIR = PACKAGE_DIR / "static"
PROMPTS_DIR = PACKAGE_DIR / "prompts"
DATA_DIR = PROJECT_ROOT / "data"
RUNTIME_DIR = DATA_DIR / "runtime"

# Local-dev webhook secret in AgentMail/Svix format ("whsec_" + base64 key).
# Only protects a server bound to 127.0.0.1; set WEBHOOK_SECRET for anything real.
DEV_WEBHOOK_SECRET = "whsec_" + base64.b64encode(b"supplier-whisperer-local-dev-only").decode("ascii")

# gpt-6-luna list prices, USD per 1M tokens (MGT 409 lecture 11).
DEFAULT_PRICES = {"input": 0.10, "cached_input": 0.01, "cache_write": 0.125, "output": 0.50}

DEFAULT_POLICY: dict = {
    "owner": {"name": "Engineer", "first_name": "Engineer", "title": "", "company": "", "inbox": ""},
    "product_name": "the product",
    "persona": {"name": "Alex", "title": "Supply Chain"},
    "assistant_signature": "Alex\nSupply Chain",
    "allowlist": [],
    "blocklist": [],
    "sensitive_terms": [],
    "defaults": {
        "risk_tolerance": "medium",
        "schedule_mode": "clock",
        "llm_mode": "auto",
        "daily_budget_usd": 1.0,
        "paused": False,
    },
    "supervised_hours": {"days": [0, 1, 2, 3, 4], "start": "09:00", "end": "17:00"},
    "limits": {
        "per_email_budget_usd": 0.05,
        "max_llm_calls_per_email": 6,
        "max_agent_replies_per_thread_per_day": 3,
    },
    "injection_threshold": 1.0,
    "suspicious_threshold": 0.4,
}


def _read_text_any(path: Path) -> str:
    """UTF-8 (with/without BOM) or UTF-16 (what Windows PowerShell 5.1 `>` writes)."""
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in _read_text_any(path).splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        if key:
            values[key] = value
    return values


def _repo_root(start: Path = PROJECT_ROOT) -> Path | None:
    for folder in start.parents:
        if (folder / ".git").exists():
            return folder
    return None


def load_env(project_root: Path = PROJECT_ROOT) -> list[Path]:
    """Load .env from the project folder, then its parent, then the enclosing git repo's root and the folder above it.

    Real environment variables win. Nearer files win over farther ones.
    Empty values never override (so a blank PORTKEY_API_KEY= copied from
    .env.example does not hide the staff key in the folder above).
    """
    loaded: list[Path] = []
    folders = [project_root, project_root.parent]
    root = _repo_root(project_root)
    # This app lives in a subfolder of a course repo (MGT409/project1/supplier-whisperer). Staff clone the whole
    # repo into submissions/ and keep their .env one level ABOVE the repo, so also check the repo root and its parent.
    for extra in ([root, root.parent] if root else []):
        if extra not in folders:
            folders.append(extra)
    for folder in folders:
        path = folder / ".env"
        if not path.is_file():
            continue
        for key, value in _parse_env_file(path).items():
            if value and not os.environ.get(key):
                os.environ[key] = value
        loaded.append(path)
    return loaded


def default_db_dir() -> Path:
    """data/runtime/ normally; a local app-data folder when the repo sits in a cloud-synced folder
    (OneDrive/Dropbox/iCloud lock SQLite journal files)."""
    synced = any(tag in str(PROJECT_ROOT).lower() for tag in ("onedrive", "dropbox", "icloud", "google drive"))
    if not synced:
        return RUNTIME_DIR
    base = os.getenv("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    return Path(base) / "SupplierWhisperer"


def resolve_dataset(name_or_path: str) -> Path:
    """A dataset is a folder with product_spec.md, emails.json and policy.json."""
    candidates = [Path(name_or_path), DATA_DIR / name_or_path]
    for candidate in candidates:
        if candidate.is_dir() and (candidate / "product_spec.md").is_file():
            return candidate.resolve()
    raise SystemExit(
        f"Dataset '{name_or_path}' not found. Expected a folder under {DATA_DIR} "
        "containing product_spec.md, emails.json and policy.json."
    )


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load_policy(dataset_dir: Path) -> dict:
    path = dataset_dir / "policy.json"
    if not path.is_file():
        return copy.deepcopy(DEFAULT_POLICY)
    with path.open(encoding="utf-8") as fh:
        return _merge(DEFAULT_POLICY, json.load(fh))


def load_sample_events(dataset_dir: Path) -> list[dict]:
    path = dataset_dir / "emails.json"
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, list) else []


@dataclass
class AppConfig:
    dataset_dir: Path
    db_path: Path
    host: str = "127.0.0.1"
    port: int = 8000
    portkey_api_key: str = ""
    portkey_base_url: str = "https://api.portkey.ai/v1"
    portkey_provider: str = "openai"
    model: str = "gpt-6-luna"
    llm_mode: str = "auto"  # auto | live | mock
    reasoning_effort: str = ""
    portkey_cache: str = ""  # "refresh" bypasses Portkey's response cache (fresh answers, real token counts)
    webhook_secret: str = DEV_WEBHOOK_SECRET
    prices: dict = field(default_factory=lambda: dict(DEFAULT_PRICES))
    env_files: list = field(default_factory=list)
    fly_private: bool = False  # bound to Fly.io's private network (--fly-private), reached only via `fly proxy`

    @property
    def live_available(self) -> bool:
        return bool(self.portkey_api_key)

    @property
    def using_dev_secret(self) -> bool:
        return self.webhook_secret == DEV_WEBHOOK_SECRET

    @classmethod
    def from_env(
        cls,
        dataset: str | None = None,
        db_path: str | None = None,
        host: str | None = None,
        port: int | None = None,
        llm_mode: str | None = None,
    ) -> "AppConfig":
        env_files = load_env()
        dataset_dir = resolve_dataset(dataset or os.getenv("DATASET", "sample"))
        db = Path(db_path or os.getenv("WHISPERER_DB") or (default_db_dir() / f"{dataset_dir.name}.db"))
        prices = dict(DEFAULT_PRICES)
        for key, env_name in (
            ("input", "PRICE_INPUT_PER_M"),
            ("cached_input", "PRICE_CACHED_INPUT_PER_M"),
            ("output", "PRICE_OUTPUT_PER_M"),
        ):
            raw = os.getenv(env_name)
            if raw:
                try:
                    prices[key] = float(raw)
                except ValueError:
                    pass
        return cls(
            dataset_dir=dataset_dir,
            db_path=db,
            host=host or os.getenv("HOST", "127.0.0.1"),
            port=int(port or os.getenv("PORT", "8000")),
            portkey_api_key=os.getenv("PORTKEY_API_KEY", "").strip(),
            portkey_base_url=os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1").rstrip("/"),
            portkey_provider=os.getenv("PORTKEY_PROVIDER", "openai").strip() or "openai",
            model=os.getenv("MODEL_NAME", "gpt-6-luna").strip() or "gpt-6-luna",
            llm_mode=(llm_mode or os.getenv("LLM_MODE", "auto")).strip().lower(),
            reasoning_effort=os.getenv("REASONING_EFFORT", "").strip(),
            portkey_cache=os.getenv("PORTKEY_CACHE", "").strip().lower(),
            webhook_secret=os.getenv("WEBHOOK_SECRET", "").strip() or DEV_WEBHOOK_SECRET,
            prices=prices,
            env_files=env_files,
        )
