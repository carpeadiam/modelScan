#!/usr/bin/env python3
import json, os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipelineguard.config import settings
from pipelineguard.store import PipelineGuardAPI
from pipelineguard.dataset import records_to_frame, validate_records

settings.validate_ingest()
records = PipelineGuardAPI(settings.api_url, settings.api_key).builds(limit=1000)
valid, rejected = validate_records(records)
frame = records_to_frame(valid)
out = Path(__file__).resolve().parents[1] / 'dataset' / 'real_pipeline_history.csv'
if not frame.empty: frame.to_csv(out, index=False)
else: print('No verified completed Cloudflare executions yet; no CSV created.')
summary = {'retrieved': len(records), 'verified_binary_records': len(valid), 'rejected': len(rejected), 'class_counts': frame['label'].value_counts().to_dict() if not frame.empty else {}}
(Path(__file__).resolve().parents[1] / 'dataset' / 'dataset_summary.json').write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
