import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from aggregate_dataset import aggregate  # noqa: E402


def aggregate_into(storage):
    import tempfile
    df, _ = aggregate(storage, local_dir=Path(tempfile.mkdtemp()))
    return df
