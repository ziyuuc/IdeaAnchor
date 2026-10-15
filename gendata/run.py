#!/usr/bin/env python3
"""Run one stage of the data generation pipeline.

  1  cleaned paper markdown  -> core idea and prior works      (LLM)
  2  stage 1 output          -> prior works with abstracts      (search.find_abstract)
  3  stage 2 output          -> synthesis narrative + proposal  (LLM)
  4  stage 3 output          -> rubrics                         (LLM)

Every stage appends to --output and skips paper IDs already written there.
"""

import argparse

from common import DEFAULT_API_CONFIG, load_api_config


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stage", type=int, required=True, choices=[1, 2, 3, 4])
    parser.add_argument("--input", required=True, help="Stage 1: folder of cleaned .md papers; stages 2-4: JSONL")
    parser.add_argument("--output", required=True, help="Output JSONL")
    parser.add_argument("--api-config", default=DEFAULT_API_CONFIG, help="API settings (default: ../api.yaml)")
    parser.add_argument("--max-papers", type=int, help="Process the first N papers")
    parser.add_argument("--concurrency", type=int, default=2, help="Parallel workers")
    args = parser.parse_args()

    config = load_api_config(args.api_config)
    common = dict(max_papers=args.max_papers, concurrency=args.concurrency)
    if args.stage == 2:
        from search import run_stage2
        run_stage2(config, args.input, args.output, **common)
    else:
        import stages
        getattr(stages, f"run_stage{args.stage}")(config, args.input, args.output, **common)


if __name__ == "__main__":
    main()
