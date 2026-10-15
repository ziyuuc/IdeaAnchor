"""LLM stages: 1) core idea and prior works, 3) synthesis and proposal, 4) rubrics."""

from pathlib import Path

from common import (LLMClient, core_idea_lines, extract_json, format_prior_works, load_prompt, logger,
                    read_jsonl, run_resumable)

MAX_TOKENS = {"extract": 16000, "proposal": 16000, "rubric": 4096}


def run_stage1(config, input_dir, output_file, max_papers=None, concurrency=2):
    """Extract the core idea and the prior works that shaped it from each cleaned paper."""
    papers = sorted(Path(input_dir).glob("*.md"))[:max_papers]
    if not papers:
        raise FileNotFoundError(f"No .md papers in {input_dir}")
    llm, system_prompt = LLMClient(config), load_prompt("extract_prior_works.md")

    def process(path):
        content = path.read_text(encoding="utf-8")
        user_prompt = ("Please analyze the following research paper and identify the key prior works that directly "
                       "influenced its core idea formation. Follow the instructions in your system prompt carefully."
                       "\n\n## Paper Content:\n\n" + content + "\n")
        logger.info("[%s] Stage 1: extracting prior works", path.stem)
        result = extract_json(llm.call(system_prompt, user_prompt, MAX_TOKENS["extract"]))
        if "core_idea" not in result:
            logger.error("[%s] no core_idea in response", path.stem)
            return None
        return {"paper_id": path.stem, "paper_path": str(path), "core_idea": result["core_idea"],
                "prior_works": result.get("prior_works", [])}

    run_resumable([{"paper_id": p.stem, "path": p} for p in papers], lambda item: process(item["path"]),
                  output_file, concurrency)


def run_stage3(config, input_file, output_file, max_papers=None, concurrency=2):
    """Generate the synthesis narrative and the reference proposal from the prior works and the paper."""
    llm, system_prompt = LLMClient(config), load_prompt("gen_synthesis_proposal.md")

    def process(record):
        content = Path(record["paper_path"]).read_text(encoding="utf-8")
        user_prompt = ("Based on the following analysis of prior works and the original paper, generate a synthesis "
                       "narrative and research proposal. Follow the format specified in your system prompt.\n\n"
                       "## Core Idea\n\n" + core_idea_lines(record["core_idea"]) + "\n\n"
                       "## Prior Works\n\n" + format_prior_works(record["prior_works"]) + "\n\n"
                       "## Original Paper (for technical detail reference)\n\n" + content)
        logger.info("[%s] Stage 3: generating synthesis and proposal", record["paper_id"])
        result = extract_json(llm.call(system_prompt, user_prompt, MAX_TOKENS["proposal"]))
        if "synthesis_narrative" not in result or "motivation" not in result:
            logger.error("[%s] response missing synthesis_narrative or motivation", record["paper_id"])
            return None
        return dict(record, synthesis_narrative=result["synthesis_narrative"],
                    proposal={"motivation": result["motivation"], "method": result.get("method", "")})

    run_resumable(read_jsonl(input_file)[:max_papers], process, output_file, concurrency)


def run_stage4(config, input_file, output_file, max_papers=None, concurrency=2):
    """Generate rubrics from the prior works, synthesis narrative, and reference proposal."""
    llm, system_prompt = LLMClient(config), load_prompt("gen_rubric.md")

    def process(record):
        proposal = record["proposal"]
        user_prompt = ("Based on the following prior works analysis, synthesis narrative, and reference proposal, "
                       "generate evaluation rubrics. Follow the instructions in your system prompt.\n\n"
                       "## Core Idea (from the paper)\n\n" + core_idea_lines(record["core_idea"]) + "\n\n"
                       "## Prior Works\n\n" + format_prior_works(record["prior_works"]) + "\n\n"
                       "## Synthesis Narrative (Thinking Process)\n\n" + record["synthesis_narrative"] + "\n\n"
                       "## Reference Proposal -- Motivation\n\n" + proposal.get("motivation", "") + "\n\n"
                       "## Reference Proposal -- Method\n\n" + proposal.get("method", "") + "\n")
        logger.info("[%s] Stage 4: generating rubrics", record["paper_id"])
        rubrics = extract_json(llm.call(system_prompt, user_prompt, MAX_TOKENS["rubric"])).get("rubrics", [])
        if not rubrics:
            logger.warning("[%s] no rubrics in response", record["paper_id"])
        return dict(record, rubrics=rubrics)

    run_resumable(read_jsonl(input_file)[:max_papers], process, output_file, concurrency)
