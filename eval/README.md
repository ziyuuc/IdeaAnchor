# Evaluation

The evaluator loads a model with vLLM, generates a research proposal for each evaluation prompt, and grades each proposal against the paper's rubrics with an API judge using the prompt in `prompts/judge.md`.

## Setup

Install the dependencies and download the evaluation prompts from the [IdeaAnchor dataset](https://huggingface.co/datasets/idealand/IdeaAnchor):

```bash
pip install -r eval/requirements.txt
hf download idealand/IdeaAnchor data/eval/prompts.jsonl --repo-type dataset --local-dir .
```

Configure the judge endpoint, API key, and model in the `eval` section of [`../api.yaml`](../api.yaml).

## Usage

Run the evaluator from the repository root. `--model` accepts a Hugging Face model ID or a local model directory.

```bash
python eval/evaluate.py --model Qwen/Qwen3-8B --data data/eval/prompts.jsonl --output-dir output/qwen3-8b
```

Generation uses temperature 0.6, top-p 0.95, up to 8192 new tokens, and seed 42 by default; each of these can be changed on the command line. Use `--limit` to evaluate a subset, `--tensor-parallel` to run on several GPUs, and `--generate-only` to skip grading. `--disable-thinking` passes `enable_thinking=False` to the chat template, and `--chat-template` supplies a template for tokenizers without one.

## Output

The output directory contains three files:

```text
generations.jsonl  # paper_id, model, response, rubrics
graded.jsonl       # generation fields plus judge_model, score, details, status
summary.json       # generation settings, status counts, mean scores
```

Thinking blocks are removed before grading. Each judgment has the status `OK`, `PARSE_FAIL`, `FAILED`, or `EMPTY_RESPONSE`. `mean_score` counts unsuccessful judgments as 0, while `mean_score_successful` averages only `OK` judgments.
