import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
DB_PATH = Path(os.getenv("ATEC_DB", ROOT / "api" / "atec.db"))

# Devin-session planning is wired but off until a service-user key is supplied.
DEVIN_API_KEY = os.getenv("DEVIN_API_KEY", "")
DEVIN_ORG_ID = os.getenv("DEVIN_ORG_ID", "")
DEVIN_API_BASE = os.getenv("DEVIN_API_BASE", "https://api.devin.ai")
DEVIN_PLANNING_ENABLED = os.getenv("DEVIN_PLANNING_ENABLED", "false").lower() == "true" and bool(DEVIN_API_KEY)
