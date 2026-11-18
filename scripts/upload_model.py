#!/usr/bin/env python3
"""Upload only locally trained artifacts produced from the verified real dataset."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipelineguard.config import settings
import requests
ROOT=Path(__file__).resolve().parents[1]
settings.validate_ingest()
model=ROOT/'artifacts'/'model.json'; evaluation=ROOT/'artifacts'/'evaluation.json'
if not model.exists() or not evaluation.exists(): raise SystemExit('Train a model first with python scripts/train_model.py')
payload={'model':json.loads(model.read_text()),'evaluation':json.loads(evaluation.read_text())}
r=requests.post(settings.api_url+'/api/model/upload',json=payload,headers={'Authorization':f'Bearer {settings.api_key}'},timeout=60)
r.raise_for_status(); print(r.json())
