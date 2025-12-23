import os
import sys
import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
)
from peft import LoraConfig, get_peft_model
from trl import SFTTrainer, SFTConfig
from pathlib import Path

# --- configuration ---
MODEL_NAME = "fdtn-ai/Foundation-Sec-8B"  # or local path if downloaded
DATA_FILE = "models/cot_dataset_v4.jsonl"  # Phase 4 = normalized labels + balanced sampling
OUTPUT_DIR = "models/adapters/cot_v4"  # v4 = normalized labels (90→74), merged platform variants

# Detect platform
IS_MPS = torch.backends.mps.is_available()
IS_CUDA = torch.cuda.is_available()

def train(resume_from_checkpoint: str = None):
    """
    Train LoRA adapter on Mac MPS or NVIDIA CUDA.

    Args:
        resume_from_checkpoint: Path to checkpoint directory to resume from (optional)
    """
    device_name = "MPS (Apple Silicon)" if IS_MPS else "CUDA" if IS_CUDA else "CPU"
    print(f"=" * 60)
    print(f"Phase 4: LoRA Training on {device_name}")
    print(f"=" * 60)

    # Validate data file exists
    if not Path(DATA_FILE).exists():
        print(f"ERROR: Training data not found: {DATA_FILE}")
        print("Run Phase 3 (synthesize_reasoning_cuda.py) first!")
        sys.exit(1)

    # Count training examples
    with open(DATA_FILE, 'r') as f:
        num_examples = sum(1 for _ in f)
    print(f"Training examples: {num_examples}")

    if num_examples < 100:
        print(f"WARNING: Only {num_examples} examples - consider generating more data")

    # 1. Load Model & Tokenizer
    print(f"\nLoading model: {MODEL_NAME}...")

    if IS_MPS:
        # Mac Apple Silicon - use float16 without quantization
        # M3 Ultra with 96GB has plenty of headroom for 16GB model
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True
        )
        print("  Using float16 on MPS (no quantization)")
    elif IS_CUDA:
        # NVIDIA GPU - use 4-bit quantization if bitsandbytes available
        try:
            from transformers import BitsAndBytesConfig
            from peft import prepare_model_for_kbit_training

            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
            )
            model = AutoModelForCausalLM.from_pretrained(
                MODEL_NAME,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True
            )
            model = prepare_model_for_kbit_training(model)
            print("  Using 4-bit QLoRA on CUDA")
        except ImportError:
            # Fallback to float16 if bitsandbytes not available
            model = AutoModelForCausalLM.from_pretrained(
                MODEL_NAME,
                torch_dtype=torch.float16,
                device_map="auto",
                trust_remote_code=True
            )
            print("  Using float16 on CUDA (bitsandbytes not available)")
    else:
        # CPU fallback (will be slow)
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            torch_dtype=torch.float32,
            trust_remote_code=True
        )
        print("  WARNING: Using CPU - training will be very slow!")

    model.config.use_cache = False  # Silence warnings during training
    model.config.pretraining_tp = 1

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"  # Fix for fp16
    
    # 2. LoRA Configuration
    peft_config = LoraConfig(
        lora_alpha=32,
        lora_dropout=0.05,
        r=16,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"]
    )

    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    # 3. Load Data
    print(f"\nLoading dataset: {DATA_FILE}")
    dataset = load_dataset("json", data_files=DATA_FILE, split="train")
    print(f"  Loaded {len(dataset)} training examples")

    # 4. Training Arguments - optimized for Mac MPS
    # With 96GB RAM and ~1500 examples, we can use larger batches
    batch_size = 4 if IS_MPS else 4  # Can increase on MPS with 96GB
    grad_accum = 4  # Effective batch = 16

    # Calculate steps for checkpointing
    total_examples = len(dataset)
    steps_per_epoch = total_examples // (batch_size * grad_accum)
    save_steps = max(25, steps_per_epoch // 4)  # ~4 checkpoints per epoch

    print(f"\nTraining configuration:")
    print(f"  Batch size: {batch_size}")
    print(f"  Gradient accumulation: {grad_accum}")
    print(f"  Effective batch: {batch_size * grad_accum}")
    print(f"  Steps per epoch: ~{steps_per_epoch}")
    print(f"  Save checkpoint every: {save_steps} steps")

    # 5. SFTConfig (trl 0.24+ API) - combines TrainingArguments with SFT-specific settings
    sft_config = SFTConfig(
        output_dir=OUTPUT_DIR,
        num_train_epochs=3,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        max_grad_norm=0.3,
        learning_rate=2e-4,
        weight_decay=0.001,
        optim="adamw_torch",  # Standard optimizer (works on all platforms)
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        group_by_length=True,
        save_steps=save_steps,
        save_total_limit=5,  # Keep last 5 checkpoints to save disk
        logging_steps=10,
        logging_first_step=True,
        fp16=not IS_MPS,  # FP16 on CUDA only
        bf16=False,
        dataloader_pin_memory=False if IS_MPS else True,  # MPS doesn't support pinned memory
        report_to="none",  # Disable wandb/tensorboard for overnight run
        # SFT-specific settings (moved from SFTTrainer constructor)
        dataset_text_field="text",
        max_length=2048,
        packing=False,
    )

    # 6. Trainer
    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        peft_config=peft_config,
        processing_class=tokenizer,
        args=sft_config,
    )

    # 7. Train (with optional resume)
    print("\n" + "=" * 60)
    print("Starting training...")
    print("=" * 60)

    if resume_from_checkpoint:
        print(f"Resuming from checkpoint: {resume_from_checkpoint}")
        trainer.train(resume_from_checkpoint=resume_from_checkpoint)
    else:
        # Check for existing checkpoints to auto-resume
        checkpoint_dirs = list(Path(OUTPUT_DIR).glob("checkpoint-*"))
        if checkpoint_dirs:
            latest_checkpoint = max(checkpoint_dirs, key=lambda p: int(p.name.split("-")[1]))
            print(f"Found existing checkpoint: {latest_checkpoint}")
            print("Auto-resuming from latest checkpoint...")
            trainer.train(resume_from_checkpoint=str(latest_checkpoint))
        else:
            trainer.train()

    # 7. Save final adapter
    print(f"\nSaving final adapter to {OUTPUT_DIR}...")
    trainer.model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

    # 8. Verify output
    adapter_file = Path(OUTPUT_DIR) / "adapter_model.safetensors"
    if adapter_file.exists():
        size_mb = adapter_file.stat().st_size / (1024 * 1024)
        print(f"  adapter_model.safetensors: {size_mb:.1f} MB")
        print("\n✅ Phase 4 Complete! Adapter saved successfully.")
    else:
        print("\n⚠️  Warning: adapter_model.safetensors not found!")
        print("Check the checkpoint directories for saved weights.")

    print(f"\nNext: Run Phase 5 (benchmark_adapter.py) to evaluate")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Phase 4: Train LoRA Adapter")
    parser.add_argument("--resume", type=str, default=None,
                        help="Path to checkpoint to resume from")
    args = parser.parse_args()

    train(resume_from_checkpoint=args.resume)
