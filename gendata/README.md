# Data generation

This pipeline builds one record per paper containing the paper's core idea, the prior works that led to it with their abstracts, a synthesis narrative, a reference proposal (motivation and method), and evaluation rubrics. The records are then converted into the SFT and RL training data.

## Setup

Run all commands from `gendata/` and install the dependencies:

```bash
pip install -r requirements.txt
```

Configure the API endpoint, API key, and model in the `gendata` section of [`../api.yaml`](../api.yaml). Create a `papers/` folder and place the PDFs in it, naming each file by the paper ID, for example `papers/ml/pdf/<openreview_id>.pdf`.

## 1. Convert papers to Markdown

For OpenReview papers, the PDFs can be downloaded from a list of OpenReview IDs. MinerU then converts the first 15 pages of each PDF to Markdown, and `clean_md.py` keeps only the title, abstract, main text, and references:

```bash
python preprocess/download_openreview.py -i openreview_ids.txt -o papers/ml/pdf
python preprocess/pdf2md.py -i papers/ml/pdf -o papers/ml/md
python preprocess/clean_md.py -i papers/ml/md -o papers/ml/md_clean
```

For Nature Communications papers, the main text is taken from article JSON files that provide `title` and `section_set`, and the references are extracted from the PDF:

```bash
python preprocess/download_nature.py -i article_ids.txt -o papers/nature/pdf
python preprocess/nature_json2md.py --json-dir papers/nature/json --pdf-dir papers/nature/pdf -o papers/nature/md
```

## 2. Generate records

The pipeline runs in four stages, each reading the output of the previous one:

```bash
python run.py --stage 1 --input papers/ml/md_clean   --output output/stage1.jsonl  # core idea and prior works
python run.py --stage 2 --input output/stage1.jsonl --output output/stage2.jsonl  # abstracts of prior works
python run.py --stage 3 --input output/stage2.jsonl --output output/stage3.jsonl  # synthesis and proposal
python run.py --stage 4 --input output/stage3.jsonl --output output/stage4.jsonl  # rubrics
```

Stage 2 looks up the abstract of each prior work with `find_abstract()` in `search.py`, which you need to implement with a paper search service of your choice (for example Semantic Scholar, OpenAlex, or arXiv). Prior works without an abstract are removed. Each stage appends to its output file and skips papers that are already in it, so an interrupted stage can be resumed with the same command. `--concurrency` sets the number of parallel requests, and `--max-papers` limits the run to the first N papers.

## 3. Convert to training data

```bash
python convert.py sft output/stage4.jsonl output/sft.jsonl
python convert.py rl  output/stage4.jsonl output/rl.jsonl
```

The output uses the ms-swift format expected by the commands in [`../train/`](../train/README.md).
