# RL

GRPO training of `Qwen/Qwen3-8B` with a rubric-based reward. The reward function in `rubric_reward.py` is loaded as an ms-swift plugin: a judge model marks each of the paper's rubrics as hit or miss, and the reward is the fraction of rubrics hit. The answer, with its thinking removed, is limited to 1024 tokens; longer answers are truncated before grading and receive a penalty of -1.0.

The setup uses three GPUs. GPU 1 runs the rollout server and GPU 2 runs the judge server:

```bash
CUDA_VISIBLE_DEVICES=1 \
swift rollout \
  --model Qwen/Qwen3-8B \
  --vllm_max_model_len 8192 \
  --vllm_gpu_memory_utilization 0.85 \
  --port 8000
```

```bash
CUDA_VISIBLE_DEVICES=2 \
vllm serve Qwen/Qwen3-8B \
  --served-model-name judge \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.85 \
  --dtype bfloat16 \
  --trust-remote-code \
  --port 8001
```

Once both servers are running, start training on GPU 0 with `DOMAIN` set to `ml` or `nc`:

```bash
DOMAIN=ml
CUDA_VISIBLE_DEVICES=0 NPROC_PER_NODE=1 \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
JUDGE_BASE_URL=http://127.0.0.1:8001/v1 \
swift rlhf \
  --rlhf_type grpo \
  --model Qwen/Qwen3-8B \
  --dataset data/train/rl/${DOMAIN}.jsonl \
  --external_plugins train/rl/rubric_reward.py \
  --reward_funcs rubric_reward \
  --tuner_type full \
  --torch_dtype bfloat16 \
  --deepspeed zero2_offload \
  --gradient_checkpointing true \
  --use_vllm true \
  --vllm_mode server \
  --vllm_server_host 127.0.0.1 \
  --vllm_server_port 8000 \
  --num_generations 8 \
  --temperature 0.7 \
  --max_completion_length 2048 \
  --max_length 8192 \
  --beta 0.0 \
  --num_train_epochs 1 \
  --per_device_train_batch_size 8 \
  --gradient_accumulation_steps 64 \
  --learning_rate 1e-6 \
  --warmup_ratio 0.05 \
  --split_dataset_ratio 0 \
  --load_from_cache_file false \
  --dataloader_num_workers 0 \
  --save_steps 10 \
  --save_total_limit 10 \
  --logging_steps 1 \
  --log_completions true \
  --output_dir output/rl_${DOMAIN}
```

Each optimizer step uses 512 completions (64 prompts with 8 completions each). Training ends at `checkpoint-117` for ML and `checkpoint-104` for NC.

The plugin reads the judge endpoint from `JUDGE_BASE_URL` (default `http://127.0.0.1:8001/v1`) and the served model name from `JUDGE_MODEL` (default `judge`). `JUDGE_API_KEY` sets an optional bearer token, and `REWARD_TOKENIZER` sets the tokenizer used for the length limit (default `Qwen/Qwen3-8B`).
