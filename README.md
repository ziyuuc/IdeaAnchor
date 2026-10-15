# IdeaAnchor: Teaching LLMs to Turn Literature into Research Ideas

<p align="left">
<a href="https://arxiv.org/abs/2610.08781"><img src="https://img.shields.io/badge/arXiv-2610.08781-red.svg"></a>
<a href="https://huggingface.co/datasets/idealand/IdeaAnchor"><img src="https://img.shields.io/badge/%F0%9F%A4%97%20Dataset-IdeaAnchor-yellow.svg"></a>
</p>

The repository contains the code for [IdeaAnchor: Teaching LLMs to Turn Literature into Research Ideas](https://arxiv.org/abs/2610.08781). It covers building the training data from papers, training models with SFT, SSD, and RL, and evaluating generated research proposals against paper-specific rubrics.

| Folder | Description |
| --- | --- |
| [`gendata/`](gendata/README.md) | Builds records with the core idea, prior works, synthesis narrative, reference proposal, and rubrics for each paper, and converts them to training data. |
| [`train/`](train/README.md) | Training commands for SFT, SSD, and RL on [ms-swift](https://github.com/modelscope/ms-swift), including the rubric reward plugin for RL. |
| [`eval/`](eval/README.md) | Generates proposals with vLLM and grades them against the rubrics with an LLM judge. |

## Setup

Each part has its own dependencies. Install the ones you need:

```bash
pip install -r gendata/requirements.txt          # data generation
pip install "ms-swift>=4.0" deepspeed vllm       # training
pip install -r eval/requirements.txt             # evaluation
```

## Data

The training and evaluation data are available on [Hugging Face](https://huggingface.co/datasets/idealand/IdeaAnchor). The dataset provides the configurations `raw` (source records), `sft`, `ssd`, and `rl` (training data for machine learning and Nature Communications papers), and `eval` and `eval_reference` (924 held-out machine learning papers).

```bash
hf download idealand/IdeaAnchor --repo-type dataset --local-dir .
```

This places the files under `data/`, where the training and evaluation commands expect them.

## Configuration

Edit [api.yaml](api.yaml) before running data generation or evaluation. Set `model` under both `gendata` and `eval`, and either put the API key in `api_key` or set the environment variable `OPENAI_API_KEY`.

Leave `base_url` empty for the default OpenAI endpoint. To use an OpenAI-compatible endpoint, set `base_url`, `api_key`, and `model` to match that provider.

## Generate Data

Run the four stages of the pipeline on papers converted to Markdown, then convert the records to training data:

```bash
cd gendata
python run.py --stage 1 --input papers/ml/md_clean   --output output/stage1.jsonl
python run.py --stage 2 --input output/stage1.jsonl --output output/stage2.jsonl
python run.py --stage 3 --input output/stage2.jsonl --output output/stage3.jsonl
python run.py --stage 4 --input output/stage3.jsonl --output output/stage4.jsonl
python convert.py sft output/stage4.jsonl output/sft.jsonl
```

See [gendata/README.md](gendata/README.md) for preparing the papers and implementing the abstract lookup used in stage 2.

## Train

Train `Qwen/Qwen3-8B` with SFT on the machine learning data:

```bash
DOMAIN=ml
CUDA_VISIBLE_DEVICES=0 NPROC_PER_NODE=1 \
swift sft \
  --model Qwen/Qwen3-8B \
  --dataset data/train/sft/${DOMAIN}.jsonl \
  --tuner_type full \
  --torch_dtype bfloat16 \
  --deepspeed zero2_offload \
  --gradient_checkpointing true \
  --num_train_epochs 5 \
  --per_device_train_batch_size 4 \
  --gradient_accumulation_steps 8 \
  --learning_rate 1e-5 \
  --warmup_ratio 0.1 \
  --max_length 8192 \
  --loss_scale ignore_empty_think \
  --split_dataset_ratio 0 \
  --load_from_cache_file false \
  --dataloader_num_workers 2 \
  --save_steps 200 \
  --save_total_limit 10 \
  --logging_steps 1 \
  --output_dir output/sft_${DOMAIN}
```

See [train/README.md](train/README.md) for SSD and RL.

## Evaluate

Generate and grade proposals for a Hugging Face model or a local checkpoint:

```bash
python eval/evaluate.py \
  --model Qwen/Qwen3-8B \
  --data data/eval/prompts.jsonl \
  --output-dir output/qwen3-8b
```

## Citation

```bibtex
@article{chen2026ideaanchor,
  title={IdeaAnchor: Teaching LLMs to Turn Literature into Research Ideas},
  author={Chen, Ziyu and Zhao, Yilun and Sun, Jiashuo and Ma, Yiling and Patwardhan, Manasi and Cohan, Arman},
  journal={arXiv preprint arXiv:2610.08781},
  year={2026}
}
```
