# SSD

SSD training uses the same settings as [SFT](../sft/README.md) and differs only in the training data (`ssd`). Set `DOMAIN` to `ml` or `nc`:

```bash
DOMAIN=ml
CUDA_VISIBLE_DEVICES=0 NPROC_PER_NODE=1 \
swift sft \
  --model Qwen/Qwen3-8B \
  --dataset data/train/ssd/${DOMAIN}.jsonl \
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
  --output_dir output/ssd_${DOMAIN}
```

Training ends at `checkpoint-1175` for ML and `checkpoint-1045` for NC.
