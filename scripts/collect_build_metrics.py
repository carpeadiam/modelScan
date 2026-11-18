#!/usr/bin/env python3
"""Collect REAL Cloud Build execution metadata into one raw JSON record per execution.

  python scripts/collect_build_metrics.py --build-id <ID>
  python scripts/collect_build_metrics.py --all          # every terminal build tagged 'pipelineguard'
"""
import _bootstrap  # noqa: F401
import argparse
import sys

from pg.buildapi import CloudBuildApi, is_terminal
from pg.config import get_settings
from pg.records import make_record, record_key, save_record
from pg.storage import get_storage


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--build-id")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--refresh", action="store_true", help="re-fetch records that already exist")
    a = ap.parse_args()
    s = get_settings()
    if not (s.use_gcp and s.project_id and s.bucket):
        sys.exit("Needs PG_USE_GCP=true, GCP_PROJECT_ID, PG_BUCKET and authenticated gcloud/ADC. No data created.")
    api, storage = CloudBuildApi(s.project_id, s.build_region), get_storage(s)
    builds = [api.get(a.build_id)] if a.build_id else api.find_by_tag("pipelineguard")
    saved = skipped = 0
    for b in builds:
        if not is_terminal(b):
            print(f"skip {b['id']}: not finished ({b.get('status')})"); skipped += 1; continue
        if storage.exists(record_key(b["id"])) and not a.refresh:
            skipped += 1; continue
        save_record(storage, make_record(api.get(b["id"]), s.project_id))  # re-fetched via get_build => verified
        saved += 1
    print(f"saved={saved} skipped={skipped}")


if __name__ == "__main__":
    main()
