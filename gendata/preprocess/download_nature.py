#!/usr/bin/env python3
"""Download Nature Communications PDFs as <article id>.pdf.

The input lists one article ID (e.g. s41467-024-12345-6) or article URL per line. With --per-year, a fixed number of
articles is sampled from each year in --years (seed 42) before downloading.
"""

import argparse
import random
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def article_ids(path):
    ids = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        match = re.search(r"(s41467-\d{3}-\d{5}-[0-9x])", line.strip())
        if match:
            ids.append(match.group(1))
    return ids


def sample_by_year(ids, years, per_year, seed=42):
    random.seed(seed)
    sampled = []
    for year in years:
        pool = [i for i in ids if i.startswith(f"s41467-{year - 2000:03d}-")]
        sampled.extend(random.sample(pool, min(per_year, len(pool))))
    return sampled


def download(article_id, output_dir):
    target = output_dir / f"{article_id}.pdf"
    if target.exists() and target.stat().st_size > 1000:
        return "skipped"
    request = urllib.request.Request(f"https://www.nature.com/articles/{article_id}.pdf",
                                     headers={"User-Agent": USER_AGENT, "Accept": "application/pdf"})
    try:
        with urllib.request.urlopen(request, timeout=60) as resp:
            data = resp.read()
    except Exception:
        return "failed"
    if len(data) <= 1000:
        return "failed"
    target.write_bytes(data)
    return "downloaded"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-i", "--input", required=True, help="Article IDs or URLs, one per line")
    parser.add_argument("-o", "--output", required=True, help="Folder for PDFs")
    parser.add_argument("--years", type=int, nargs="+", default=[2023, 2024, 2025])
    parser.add_argument("--per-year", type=int, help="Sample this many articles per year")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    ids = article_ids(args.input)
    if args.per_year:
        ids = sample_by_year(ids, args.years, args.per_year)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda i: download(i, output), ids))
    print(f"Articles: {len(ids)}; " + ", ".join(f"{s}={results.count(s)}" for s in sorted(set(results))))


if __name__ == "__main__":
    main()
