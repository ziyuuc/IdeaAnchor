# Training

All training is done with [ms-swift](https://github.com/modelscope/ms-swift) 4.x; this folder provides the commands and the RL reward plugin. Each method fine-tunes `Qwen/Qwen3-8B`, with a separate model for each domain (`ml` and `nc`).

| Folder | Method | ms-swift entry point |
| --- | --- | --- |
| [`sft/`](sft/README.md) | Supervised fine-tuning | `swift sft` |
| [`ssd/`](ssd/README.md) | Self-distillation (SFT on the SSD data) | `swift sft` |
| [`rl/`](rl/README.md) | GRPO with a rubric-based reward | `swift rlhf` with `rubric_reward.py` |

## Setup

Install ms-swift with DeepSpeed and vLLM, then download the training data from the [IdeaAnchor dataset](https://huggingface.co/datasets/idealand/IdeaAnchor):

```bash
pip install "ms-swift>=4.0" deepspeed vllm
hf download idealand/IdeaAnchor --repo-type dataset --local-dir . \
  --include "data/train/sft/*.jsonl" "data/train/ssd/*.jsonl" "data/train/rl/*.jsonl"
```

Run all training commands from the repository root. The experiments used ms-swift 4.0, vLLM 0.10.2, transformers 4.57, and DeepSpeed 0.18.

## Multiple GPUs

The commands train on a single GPU. To train on N GPUs, set `NPROC_PER_NODE=N`, list the devices in `CUDA_VISIBLE_DEVICES`, and divide `--gradient_accumulation_steps` by N to keep the global batch size unchanged.

## Evaluation

Checkpoints are saved as Hugging Face model directories and can be passed directly to the evaluator:

```bash
python eval/evaluate.py --model output/sft_ml/<run>/checkpoint-1175 --data data/eval/prompts.jsonl --output-dir output/eval/sft_ml
```
