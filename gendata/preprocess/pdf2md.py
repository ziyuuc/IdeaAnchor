#!/usr/bin/env python3
"""Convert PDFs to text-only Markdown with MinerU, writing <output>/<pdf stem>.md.

Only the first --max-pages pages are parsed. Several GPUs can process a folder in parallel.
"""

import argparse
import logging
import os
import shutil
import tempfile
from multiprocessing import Process, Queue
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def convert(pdf_path, output_dir, max_pages, backend, method, lang, vllm_kwargs=None):
    from mineru.cli.common import do_parse, read_fn
    from mineru.utils.enum_class import MakeMode

    pdf_path, output_dir = Path(pdf_path), Path(output_dir)
    target = output_dir / f"{pdf_path.stem}.md"
    if target.exists():
        return True
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_dir) as work:
        try:
            do_parse(
                output_dir=work, pdf_file_names=[pdf_path.stem], pdf_bytes_list=[read_fn(pdf_path)],
                p_lang_list=[lang], backend=backend, parse_method=method, formula_enable=True, table_enable=True,
                start_page_id=0, end_page_id=max_pages - 1, f_dump_md=True, f_dump_middle_json=False,
                f_dump_model_output=False, f_dump_orig_pdf=False, f_dump_content_list=False,
                f_draw_layout_bbox=False, f_draw_span_bbox=False, f_make_md_mode=MakeMode.NLP_MD,
                **(vllm_kwargs or {}))
            produced = next(Path(work).rglob(f"{pdf_path.stem}.md"))
            shutil.move(str(produced), target)
        except Exception as exc:
            logger.error(f"Failed {pdf_path.name}: {exc}")
            return False
    logger.info(f"Converted {pdf_path.name}")
    return True


def worker(gpu_id, queue, options):
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    while (pdf := queue.get()) is not None:
        convert(pdf, **options)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-i", "--input", required=True, help="PDF file or folder of PDFs")
    parser.add_argument("-o", "--output", required=True, help="Folder for Markdown files")
    parser.add_argument("--max-pages", type=int, default=15)
    parser.add_argument("--backend", default="pipeline", choices=["pipeline", "hybrid-auto-engine", "hybrid-http-client"])
    parser.add_argument("--method", default="auto", choices=["auto", "txt", "ocr"])
    parser.add_argument("--lang", default="en")
    parser.add_argument("--num-gpus", type=int, default=1)
    parser.add_argument("--gpu-memory-utilization", type=float, help="vLLM setting for hybrid backends")
    args = parser.parse_args()

    source = Path(args.input)
    pdfs = [source] if source.is_file() else sorted(source.glob("*.pdf"))
    vllm_kwargs = {"gpu_memory_utilization": args.gpu_memory_utilization} if args.gpu_memory_utilization else None
    options = dict(output_dir=args.output, max_pages=args.max_pages, backend=args.backend, method=args.method,
                   lang=args.lang, vllm_kwargs=vllm_kwargs)
    if args.num_gpus <= 1:
        for pdf in pdfs:
            convert(pdf, **options)
        return
    queue = Queue()
    for pdf in pdfs:
        queue.put(str(pdf))
    for _ in range(args.num_gpus):
        queue.put(None)
    workers = [Process(target=worker, args=(gpu, queue, options)) for gpu in range(args.num_gpus)]
    for process in workers:
        process.start()
    for process in workers:
        process.join()


if __name__ == "__main__":
    main()
