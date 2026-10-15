#!/usr/bin/env python3
"""Convert stage 4 records into ms-swift SFT or RL (GRPO) training data.

SFT: system + prior works -> <think> synthesis </think> <motivation> ... </motivation> <method> ... </method>
RL:  system + prior works, with the rubrics as a JSON string column for the reward function
The prior works in each prompt are shuffled with a fixed seed.
"""

import argparse
import json
import random

BASE_SYSTEM = (
    "You are a research scientist skilled at synthesizing ideas from existing literature into novel research "
    "proposals. You are given a set of related research papers (with titles and abstracts). Your task is to "
    "analyze these papers, identify research gaps and opportunities, and propose a novel research idea."
)
RL_SYSTEM = BASE_SYSTEM + (
    " When referencing prior works, use its `@cite_id` (e.g., @chen2020simclr).\n\n"
    "Structure your response as:\n"
    "1. <motivation> and </motivation> tags — explain the research gap and why this problem matters\n"
    "2. <method> and </method> tags — describe your proposed approach in detail\n\n"
    "Place your actual content directly inside each tag pair."
)


def prior_works_prompt(prior_works, heading):
    works = prior_works[:]
    random.shuffle(works)
    return "\n\n".join(
        f"{heading} {w.get('title', 'Unknown Title')} ({w.get('cite_id', 'unknown_id')})\n"
        f"## Summary: {w.get('abstract', 'No abstract available.')}"
        for w in works)


def to_sft(record):
    proposal = record.get("proposal", {})
    answer = (f"<think>\n{record.get('synthesis_narrative', '')}\n</think>\n\n"
              f"<motivation>\n{proposal.get('motivation', '')}\n</motivation>\n\n"
              f"<method>\n{proposal.get('method', '')}\n</method>")
    return {"messages": [{"role": "system", "content": BASE_SYSTEM},
                         {"role": "user", "content": prior_works_prompt(record.get("prior_works", []), "#")},
                         {"role": "assistant", "content": answer}],
            "paper_id": record["paper_id"]}


def to_rl(record):
    rubrics = [{"id": r["id"], "category": r["category"], "criterion": r["criterion"]} for r in record["rubrics"]]
    return {"messages": [{"role": "system", "content": RL_SYSTEM},
                         {"role": "user", "content": prior_works_prompt(record.get("prior_works", []), "##")}],
            "rubrics": json.dumps(rubrics, ensure_ascii=False),
            "paper_id": record["paper_id"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("format", choices=["sft", "rl"])
    parser.add_argument("input", help="Stage 4 output JSONL")
    parser.add_argument("output", help="Training JSONL")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    convert = to_sft if args.format == "sft" else to_rl
    count = 0
    with open(args.input, encoding="utf-8") as source, open(args.output, "w", encoding="utf-8") as target:
        for line in source:
            if line.strip():
                target.write(json.dumps(convert(json.loads(line)), ensure_ascii=False) + "\n")
                count += 1
    print(f"Wrote {count} {args.format} records to {args.output}")


if __name__ == "__main__":
    main()
