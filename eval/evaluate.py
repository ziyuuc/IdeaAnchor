#!/usr/bin/env python3
"""Load a model, generate research proposals, and score them against rubrics."""

import argparse
import asyncio
import json
import time
from pathlib import Path

from judge import grade_records, make_client


def load_samples(path, limit=None):
    samples, seen = [], set()
    with Path(path).open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not row.get("paper_id") or row["paper_id"] in seen:
                raise ValueError(f"Missing or duplicate paper_id at line {number}")
            if not row.get("messages") or any(m.get("role") not in {"system", "user"} for m in row["messages"]):
                raise ValueError(f"Expected system/user evaluation messages at line {number}")
            if not any(m["role"] == "user" and m.get("content", "").strip() for m in row["messages"]):
                raise ValueError(f"Missing user input at line {number}")
            rubrics = row.get("rubrics")
            if isinstance(rubrics, str):
                rubrics = json.loads(rubrics)
            if not isinstance(rubrics, list) or not rubrics:
                raise ValueError(f"Missing evaluation rubrics at line {number}")
            if any(not {"id", "category", "criterion"} <= set(r) for r in rubrics):
                raise ValueError(f"Invalid rubric fields at line {number}")
            samples.append({"paper_id": row["paper_id"], "messages": row["messages"], "rubrics": rubrics})
            seen.add(row["paper_id"])
            if limit is not None and len(samples) >= limit:
                break
    if not samples:
        raise ValueError("Evaluation data is empty")
    return samples


def generate(samples, args):
    from vllm import LLM, SamplingParams

    llm = LLM(model=args.model, tensor_parallel_size=args.tensor_parallel,
              max_model_len=args.max_model_len, gpu_memory_utilization=args.gpu_memory_utilization,
              seed=args.seed)
    sampling = SamplingParams(temperature=args.temperature, top_p=args.top_p,
                              max_tokens=args.max_tokens, seed=args.seed)
    options = {}
    if args.chat_template:
        options["chat_template"] = args.chat_template.read_text(encoding="utf-8")
    if args.disable_thinking:
        options["chat_template_kwargs"] = {"enable_thinking": False}
    started = time.perf_counter()
    outputs = llm.chat([row["messages"] for row in samples], sampling, **options)
    records = []
    for row, output in zip(samples, outputs, strict=True):
        records.append({"paper_id": row["paper_id"], "model": args.model,
                        "response": output.outputs[0].text if output.outputs else "",
                        "rubrics": row["rubrics"]})
    return records, time.perf_counter() - started


async def run(args):
    samples = load_samples(args.data, args.limit)
    client, judge_model = None, None
    if not args.generate_only:
        if not args.grader_prompt.is_file():
            raise ValueError(f"Grader prompt does not exist: {args.grader_prompt}")
        client, judge_model = make_client(args.api_config)
    try:
        records, elapsed = generate(samples, args)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        with (args.output_dir / "generations.jsonl").open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        summary = {
            "model": args.model, "data": str(args.data), "num_samples": len(records),
            "nonempty_responses": sum(bool(r["response"].strip()) for r in records),
            "generation_seconds": elapsed,
            "generation_config": {"temperature": args.temperature, "top_p": args.top_p,
                                  "max_tokens": args.max_tokens, "seed": args.seed,
                                  "max_model_len": args.max_model_len, "tensor_parallel": args.tensor_parallel,
                                  "disable_thinking": args.disable_thinking,
                                  "chat_template": str(args.chat_template) if args.chat_template else None},
        }
        if client is not None:
            summary["grading"] = await grade_records(
                client, judge_model, records, args.output_dir / "graded.jsonl", args.grader_prompt,
                concurrency=args.judge_concurrency, max_retries=args.judge_retries,
                extra_body=args.judge_extra_body,
            )
        (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return summary
    finally:
        if client is not None:
            await client.close()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Hugging Face model ID or local model directory")
    parser.add_argument("--data", type=Path, required=True, help="Evaluation prompts JSONL")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, help="Evaluate the first N records")
    parser.add_argument("--temperature", type=float, default=0.6)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-model-len", type=int, default=16384)
    parser.add_argument("--tensor-parallel", type=int, default=1)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.9)
    parser.add_argument("--chat-template", type=Path, help="Optional chat template for the model tokenizer")
    parser.add_argument("--disable-thinking", action="store_true", help="Pass enable_thinking=False to the chat template")
    parser.add_argument("--generate-only", action="store_true", help="Generate proposals without API grading")
    parser.add_argument("--api-config", type=Path, default=Path(__file__).resolve().parent.parent / "api.yaml",
                        help="Judge API settings (default: ../api.yaml)")
    parser.add_argument("--judge-concurrency", type=int, default=8)
    parser.add_argument("--judge-retries", type=int, default=3)
    parser.add_argument("--judge-extra-body", type=json.loads, help="JSON object with extra judge API parameters")
    parser.add_argument("--grader-prompt", type=Path, default=Path(__file__).resolve().parent / "prompts/judge.md")
    args = parser.parse_args(argv)
    for name in ["limit", "max_tokens", "max_model_len", "tensor_parallel", "judge_concurrency", "judge_retries"]:
        if getattr(args, name) is not None and getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if args.temperature < 0 or not 0 < args.top_p <= 1 or not 0 < args.gpu_memory_utilization <= 1:
        parser.error("Check temperature, top-p, and gpu-memory-utilization")
    if args.judge_extra_body is not None and not isinstance(args.judge_extra_body, dict):
        parser.error("--judge-extra-body must be a JSON object")
    return args


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
