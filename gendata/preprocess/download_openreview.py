#!/usr/bin/env python3
"""Download OpenReview PDFs as <openreview_id>.pdf.

The input is a text file with one OpenReview ID per line, or a JSON list of objects with an `openreview_id` field.
"""

import argparse
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def read_ids(path):
    text = Path(path).read_text(encoding="utf-8")
    if path.endswith(".json"):
        return [row["openreview_id"] for row in json.loads(text)]
    return [line.strip() for line in text.splitlines() if line.strip()]


class Downloader:
    def __init__(self, output_dir, rate_limit, max_retries, token=None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.rate_limit, self.max_retries = rate_limit, max_retries
        self.lock, self.request_times = threading.Lock(), []
        self.session = requests.Session()
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def wait_for_rate_limit(self):
        with self.lock:
            now = time.time()
            self.request_times = [t for t in self.request_times if now - t < 60]
            if len(self.request_times) >= self.rate_limit:
                time.sleep(max(0.0, 60 - (now - self.request_times[0]) + 0.1))
            self.request_times.append(time.time())

    def download(self, paper_id):
        path = self.output_dir / f"{paper_id}.pdf"
        if path.exists() and path.stat().st_size > 0:
            return "skipped"
        for attempt in range(self.max_retries):
            try:
                self.wait_for_rate_limit()
                resp = self.session.get(f"https://openreview.net/pdf?id={paper_id}", timeout=30, stream=True)
                if resp.status_code in (403, 404):
                    logger.error("%s: HTTP %d", paper_id, resp.status_code)
                    return "failed"
                resp.raise_for_status()
                if "application/pdf" not in resp.headers.get("Content-Type", ""):
                    logger.warning("%s: not a PDF", paper_id)
                    return "failed"
                with path.open("wb") as handle:
                    for chunk in resp.iter_content(chunk_size=8192):
                        handle.write(chunk)
                if path.stat().st_size < 1000:
                    path.unlink()
                    raise ValueError("downloaded file too small")
                return "downloaded"
            except Exception as exc:
                logger.warning("%s: attempt %d/%d failed: %s", paper_id, attempt + 1, self.max_retries, exc)
                time.sleep(2 ** attempt)
        return "failed"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-i", "--input", required=True, help="OpenReview IDs (.txt) or paper list (.json)")
    parser.add_argument("-o", "--output", required=True, help="Folder for PDFs")
    parser.add_argument("--rate-limit", type=int, default=300, help="Requests per minute")
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--max-workers", type=int, default=10)
    parser.add_argument("--token", help="OpenReview API token, if needed")
    parser.add_argument("--limit", type=int, help="Download the first N papers")
    args = parser.parse_args()

    ids = read_ids(args.input)[:args.limit]
    downloader = Downloader(args.output, args.rate_limit, args.max_retries, args.token)
    with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        results = list(pool.map(downloader.download, ids))
    logger.info("Papers: %d; %s", len(ids), {s: results.count(s) for s in sorted(set(results))})


if __name__ == "__main__":
    main()
