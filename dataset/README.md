# Real execution dataset

This directory intentionally contains no observations. Records are generated only after a genuine Cloudflare Workers Build has completed and its outcome has been verified. Run `python scripts/export_dataset.py` to create `real_pipeline_history.csv` from the configured D1 database. Never hand-edit this file or populate it with mocked data.
