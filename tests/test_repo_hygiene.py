import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_no_dataset_or_storage_content_shipped():
    for d in ("dataset", "storage", "reports", "workspace"):
        files = [p.name for p in (ROOT / d).rglob("*") if p.is_file()]
        assert files in ([], [".gitkeep"]), f"{d}/ contains pre-populated files: {files}"


def test_no_secrets_or_env_files():
    patterns = [r"-----BEGIN (RSA |EC )?PRIVATE KEY-----", r'"private_key"\s*:', r"AIza[0-9A-Za-z_\-]{35}", r"ya29\.[0-9A-Za-z_\-]+"]
    for p in ROOT.rglob("*"):
        if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts and p.suffix not in {".png", ".joblib"}:
            if p.name == ".env":
                raise AssertionError(".env must not be shipped")
            text = p.read_text(errors="ignore")
            for pat in patterns:
                assert not re.search(pat, text) or p.name == "test_repo_hygiene.py", f"possible secret in {p}"


def test_no_random_labels_in_pipeline_code():
    """Outcomes may only come from Cloud Build; library/ML code must not generate them randomly."""
    for f in list((ROOT / "pg").glob("*.py")) + list((ROOT / "ml").glob("*.py")) + list((ROOT / "app").glob("*.py")):
        if f.name in ("workload.py", "scenarios.py"):   # seeded experimental-design inputs (change size, scenario ORDER); never outcomes
            continue
        txt = f.read_text()
        assert "import random" not in txt and "np.random" not in txt, f.name
    wl = (ROOT / "pg/workload.py").read_text()
    assert "pipeline_status" not in wl and "FAILURE" not in wl
    sc = (ROOT / "pg/scenarios.py").read_text()
    assert "random.Random" in sc and "random.random()" not in sc and "random.choice" not in sc
