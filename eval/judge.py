"""Rubric scoring for generated research proposals."""

import asyncio
import json
import os
import re
from collections import Counter
from pathlib import Path


def strip_thinking(text):
    text = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL)
    return re.sub(r"<think>.*", "", text, flags=re.DOTALL).strip()


def build_user_prompt(response, rubrics):
    criteria = "\n".join(f"- Rubric {r['id']} ({r['category']}): {r['criterion']}" for r in rubrics)
    return f"## Proposal\n\n{strip_thinking(response)}\n\n## Rubrics\n\n{criteria}\n\nEvaluate each rubric and return the JSON."


def extract_json(response):
    text = strip_thinking(response)
    fence = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    brace = re.search(r"\{[\s\S]*\}", text)
    if not brace:
        return {}
    try:
        return json.loads(brace.group(0))
    except json.JSONDecodeError:
        try:
            return json.loads(re.sub(r",\s*([}\]])", r"\1", brace.group(0)))
        except json.JSONDecodeError:
            return {}


def parse_score(result):
    """Retain the original evaluator's score calculation."""
    details = [{"id": r.get("id", "?"), "hit": r.get("hit", 0), "reason": r.get("reason", "")}
               for r in result.get("rubrics", [])]
    if "total_score" in result and "max_score" in result:
        maximum = result["max_score"]
        score = result["total_score"] / maximum if maximum > 0 else 0.0
    else:
        score = sum(r["hit"] for r in details) / len(details) if details else 0.0
    return score, details


def make_client(api_config):
    """Build the judge client from the shared OpenAI-compatible API settings."""
    import yaml
    from openai import AsyncOpenAI

    config = (yaml.safe_load(Path(api_config).read_text(encoding="utf-8")) or {}).get("eval") or {}
    key = config.get("api_key") or os.environ.get("OPENAI_API_KEY")
    model = config.get("model")
    if not key or not model:
        raise ValueError(f"Set eval.api_key (or OPENAI_API_KEY) and eval.model in {api_config}")
    return AsyncOpenAI(api_key=key, base_url=config.get("base_url") or None), model


async def grade_one(client, judge_model, record, prompt, semaphore, max_retries, extra_body):
    if not strip_thinking(record["response"]):
        return {"score": 0.0, "details": [], "status": "EMPTY_RESPONSE"}
    messages = [{"role": "system", "content": prompt},
                {"role": "user", "content": build_user_prompt(record["response"], record["rubrics"])}]
    status = "FAILED"
    async with semaphore:
        for attempt in range(max_retries):
            try:
                response = await client.chat.completions.create(
                    model=judge_model, messages=messages, max_completion_tokens=4096,
                    extra_body=extra_body or None,
                )
            except Exception:
                status = "FAILED"
            else:
                status = "PARSE_FAIL"
                result = extract_json(response.choices[0].message.content or "")
                try:
                    if isinstance(result, dict) and (result.get("rubrics") or {"total_score", "max_score"} <= set(result)):
                        score, details = parse_score(result)
                        return {"score": score, "details": details, "status": "OK"}
                except (TypeError, ValueError, AttributeError):
                    pass
            if attempt + 1 < max_retries:
                await asyncio.sleep(min(2 ** attempt, 8))
    return {"score": 0.0, "details": [], "status": status}


async def grade_records(client, judge_model, records, output, prompt_path, concurrency=8,
                        max_retries=3, extra_body=None):
    prompt_path = Path(prompt_path)
    prompt = prompt_path.read_text(encoding="utf-8").strip()
    semaphore = asyncio.Semaphore(concurrency)
    judgments = await asyncio.gather(*[
        grade_one(client, judge_model, record, prompt, semaphore, max_retries, extra_body)
        for record in records
    ])
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for record, judgment in zip(records, judgments, strict=True):
            handle.write(json.dumps(dict(record, judge_model=judge_model, grader_prompt=prompt_path.stem, **judgment), ensure_ascii=False) + "\n")
    counts = Counter(judgment["status"] for judgment in judgments)
    successful = [r["score"] for r in judgments if r["status"] == "OK"]
    return {
        "judge_model": judge_model, "grader_prompt": prompt_path.stem, "total": len(records),
        "status_counts": dict(counts),
        "mean_score": sum(r["score"] for r in judgments) / len(judgments) if judgments else 0.0,
        "mean_score_successful": sum(successful) / len(successful) if successful else None,
    }
