"""Shared helpers: API client, prompts, JSON parsing, and resumable JSONL processing."""

import json
import logging
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
DEFAULT_API_CONFIG = ROOT.parent / "api.yaml"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("gendata")


def load_api_config(path=DEFAULT_API_CONFIG):
    """Return the `gendata` section of the API settings."""
    with open(path, encoding="utf-8") as handle:
        config = (yaml.safe_load(handle) or {}).get("gendata") or {}
    config["api_key"] = config.get("api_key") or os.environ.get("OPENAI_API_KEY", "")
    return config


class LLMClient:
    """Thread-safe OpenAI-compatible chat client."""

    def __init__(self, config, temperature=1.0):
        from openai import OpenAI

        if not config.get("api_key") or not config.get("model"):
            raise ValueError("Set gendata.api_key (or OPENAI_API_KEY) and gendata.model in api.yaml")
        self.client = OpenAI(api_key=config["api_key"], base_url=config.get("base_url") or None, max_retries=15, timeout=300.0)
        self.model = config["model"]
        self.temperature = temperature

    def call(self, system_prompt, user_prompt, max_tokens):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=self.temperature,
            max_completion_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()


def load_prompt(name):
    return (ROOT / "prompts" / name).read_text(encoding="utf-8")


def extract_json(response):
    """Parse the JSON object in an LLM response, with or without a code fence."""
    fence = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response, re.DOTALL)
    brace = re.search(r"\{.*\}", response, re.DOTALL)
    if not fence and not brace:
        return {}
    try:
        return json.loads(fence.group(1).strip() if fence else brace.group(0))
    except json.JSONDecodeError as exc:
        logger.warning("JSON parse error: %s", exc)
        return {}


def format_prior_works(prior_works):
    """Format prior works for the generation and rubric prompts."""
    entries = []
    for work in prior_works:
        entry = "- **@{}** | {} ({}, {})\n  Role: {}\n  Learned: {}".format(
            work["cite_id"], work["title"], work["authors"], work["year"], work["role"], work["what_authors_learned"])
        if work.get("abstract"):
            entry += "\n  Abstract: " + work["abstract"]
        entries.append(entry)
    return "\n\n".join(entries)


def core_idea_lines(core_idea):
    return ("- **Innovation**: {}\n- **Departure**: {}\n- **Key Insight**: {}".format(
        core_idea.get("innovation", ""), core_idea.get("departure", ""), core_idea.get("key_insight", "")))


def title_similarity(a, b):
    words_a, words_b = set(a.lower().split()), set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / max(len(words_a), len(words_b))


def read_jsonl(path):
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def run_resumable(items, process, output_file, concurrency, key=lambda item: item["paper_id"]):
    """Process items in parallel, appending results to output_file and skipping IDs already written."""
    output = Path(output_file)
    done = {row["paper_id"] for row in read_jsonl(output)} if output.exists() else set()
    todo = [item for item in items if key(item) not in done]
    logger.info("Total %d, already done %d, to process %d", len(items), len(done), len(todo))
    output.parent.mkdir(parents=True, exist_ok=True)
    lock, written, failed = threading.Lock(), 0, []
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        futures = {pool.submit(process, item): key(item) for item in todo}
        for future in as_completed(futures):
            item_id = futures[future]
            try:
                result = future.result()
            except NotImplementedError:
                raise
            except Exception as exc:
                logger.error("[%s] failed: %s", item_id, exc)
                result = None
            if result is None:
                failed.append(item_id)
                continue
            with lock, output.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(result, ensure_ascii=False) + "\n")
            written += 1
    logger.info("Wrote %d records to %s; failed %d%s", written, output, len(failed),
                f": {sorted(failed)}" if failed else "")
