from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"

RAW_DATA = DATA_DIR / "raw"
PROCESSED_DATA = DATA_DIR / "processed"

CHECKPOINTS = PROJECT_ROOT / "checkpoints"
LOGS = PROJECT_ROOT / "logs"
OUTPUTS = PROJECT_ROOT / "outputs"

DEVICE = "cuda"
