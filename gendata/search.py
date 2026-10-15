"""Stage 2: add an abstract to each prior work and drop prior works without one."""

from common import logger, read_jsonl, run_resumable


def find_abstract(work):
    """Return the abstract of a prior work, or None if it cannot be found.

    `work` is a prior-work entry from stage 1 with `title`, `authors`, `year`, and `cite_id`. Implement this function
    with the paper search service of your choice, such as Semantic Scholar, OpenAlex, or arXiv.
    """
    raise NotImplementedError("Implement find_abstract() in gendata/search.py")


def run_stage2(config, input_file, output_file, max_papers=None, concurrency=2):
    def process(record):
        kept = []
        for work in record.get("prior_works") or []:
            abstract = find_abstract(work)
            if abstract:
                kept.append(dict(work, abstract=abstract))
            else:
                logger.info("  [%s] no abstract, dropped: %s", record["paper_id"], (work.get("title") or "")[:60])
        logger.info("[%s] Stage 2: kept %d/%d prior works", record["paper_id"], len(kept), len(record.get("prior_works") or []))
        return dict(record, prior_works=kept)

    run_resumable(read_jsonl(input_file)[:max_papers], process, output_file, concurrency)
