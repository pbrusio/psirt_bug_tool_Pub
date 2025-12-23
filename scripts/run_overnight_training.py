#!/usr/bin/env python3
"""
Overnight Training Pipeline for cot_v4
======================================

This script chains Phase 3 (synthesis) -> Phase 4 (training) -> Phase 5 (benchmark)
with comprehensive pre-flight checks and graceful error handling.

Features:
- Pre-flight validation before each phase
- Automatic resume from checkpoints
- Detailed logging to file
- Graceful failure handling
- Progress notifications

Usage:
    python scripts/run_overnight_training.py           # Full pipeline
    python scripts/run_overnight_training.py --test    # Quick test (5 examples)
    python scripts/run_overnight_training.py --phase 4 # Start from specific phase
"""

import os
import sys
import json
import time
import torch
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Configuration
MODEL_NAME = "fdtn-ai/Foundation-Sec-8B"
INPUT_DATA = PROJECT_ROOT / "models/labeled_examples_normalized.parquet"
ANTI_DEFINITIONS = PROJECT_ROOT / "output/taxonomy_anti_definitions.yml"
COT_OUTPUT = PROJECT_ROOT / "models/cot_dataset_v4.jsonl"
ADAPTER_OUTPUT = PROJECT_ROOT / "models/adapters/cot_v4"
GOLD_EVAL = PROJECT_ROOT / "models/gold_standard_eval_normalized.jsonl"
LOG_FILE = PROJECT_ROOT / "overnight_training.log"

# Minimum requirements
MIN_TRAINING_EXAMPLES = 500  # Need at least 500 to proceed to training
MIN_RAM_GB = 24  # Need at least 24GB for comfortable operation


def log(message: str, also_print: bool = True):
    """Log message to file and optionally print."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"

    with open(LOG_FILE, 'a') as f:
        f.write(log_entry + "\n")

    if also_print:
        print(log_entry)


def check_system_resources() -> dict:
    """Check system resources are sufficient."""
    results = {
        "mps_available": torch.backends.mps.is_available(),
        "cuda_available": torch.cuda.is_available(),
        "device": "unknown",
        "ram_gb": 0,
        "errors": []
    }

    # Check device
    if results["mps_available"]:
        results["device"] = "mps"
    elif results["cuda_available"]:
        results["device"] = "cuda"
        # Check CUDA memory
        try:
            gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            results["gpu_memory_gb"] = gpu_mem
        except:
            pass
    else:
        results["device"] = "cpu"
        results["errors"].append("No GPU available - training will be very slow")

    # Check RAM (rough estimate via psutil if available)
    try:
        import psutil
        results["ram_gb"] = psutil.virtual_memory().total / (1024**3)
        if results["ram_gb"] < MIN_RAM_GB:
            results["errors"].append(f"RAM ({results['ram_gb']:.1f}GB) below recommended {MIN_RAM_GB}GB")
    except ImportError:
        results["ram_gb"] = -1  # Unknown

    return results


def check_input_files() -> dict:
    """Verify all input files exist and are valid."""
    results = {"errors": [], "warnings": []}

    # Check normalized training data
    if not INPUT_DATA.exists():
        results["errors"].append(f"Training data missing: {INPUT_DATA}")
    else:
        try:
            import pandas as pd
            df = pd.read_parquet(INPUT_DATA)
            results["training_rows"] = len(df)
            if len(df) < 100:
                results["errors"].append(f"Training data too small: {len(df)} rows")
        except Exception as e:
            results["errors"].append(f"Cannot read training data: {e}")

    # Check anti-definitions
    if not ANTI_DEFINITIONS.exists():
        results["errors"].append(f"Anti-definitions missing: {ANTI_DEFINITIONS}")

    # Check gold eval
    if not GOLD_EVAL.exists():
        results["warnings"].append(f"Gold eval missing: {GOLD_EVAL} (benchmark will fail)")
    else:
        try:
            with open(GOLD_EVAL) as f:
                results["gold_eval_count"] = sum(1 for _ in f)
        except:
            pass

    return results


def check_model_availability() -> dict:
    """Check if model can be loaded (without actually loading it)."""
    results = {"errors": [], "warnings": []}

    # Check if model is cached locally
    from huggingface_hub import try_to_load_from_cache
    try:
        cache_path = try_to_load_from_cache(MODEL_NAME, "config.json")
        if cache_path is not None:
            results["model_cached"] = True
            results["cache_path"] = str(Path(cache_path).parent)
        else:
            results["model_cached"] = False
            results["warnings"].append(f"Model not cached - will download ~16GB on first run")
    except Exception as e:
        results["warnings"].append(f"Cannot check model cache: {e}")
        results["model_cached"] = "unknown"

    return results


def check_dependencies() -> dict:
    """Verify all required packages are installed."""
    results = {"errors": [], "missing": []}

    required = [
        ("torch", "torch"),
        ("transformers", "transformers"),
        ("peft", "peft"),
        ("trl", "trl"),
        ("datasets", "datasets"),
        ("pandas", "pandas"),
        ("tqdm", "tqdm"),
        ("yaml", "pyyaml"),
    ]

    for import_name, pip_name in required:
        try:
            __import__(import_name)
        except ImportError:
            results["missing"].append(pip_name)
            results["errors"].append(f"Missing package: {pip_name}")

    return results


def run_preflight_checks(verbose: bool = True) -> bool:
    """Run all pre-flight checks. Returns True if ready to proceed."""
    log("=" * 60)
    log("PRE-FLIGHT CHECKS")
    log("=" * 60)

    all_errors = []
    all_warnings = []

    # 1. System resources
    if verbose:
        log("\n[1/4] Checking system resources...")
    sys_check = check_system_resources()
    log(f"  Device: {sys_check['device'].upper()}")
    if sys_check['ram_gb'] > 0:
        log(f"  RAM: {sys_check['ram_gb']:.1f} GB")
    all_errors.extend(sys_check.get("errors", []))

    # 2. Input files
    if verbose:
        log("\n[2/4] Checking input files...")
    file_check = check_input_files()
    if "training_rows" in file_check:
        log(f"  Training data: {file_check['training_rows']} rows")
    if "gold_eval_count" in file_check:
        log(f"  Gold eval: {file_check['gold_eval_count']} examples")
    all_errors.extend(file_check.get("errors", []))
    all_warnings.extend(file_check.get("warnings", []))

    # 3. Model availability
    if verbose:
        log("\n[3/4] Checking model availability...")
    model_check = check_model_availability()
    log(f"  Model cached: {model_check.get('model_cached', 'unknown')}")
    all_errors.extend(model_check.get("errors", []))
    all_warnings.extend(model_check.get("warnings", []))

    # 4. Dependencies
    if verbose:
        log("\n[4/4] Checking dependencies...")
    dep_check = check_dependencies()
    if dep_check["missing"]:
        log(f"  Missing: {', '.join(dep_check['missing'])}")
    else:
        log(f"  All dependencies installed")
    all_errors.extend(dep_check.get("errors", []))

    # Summary
    log("\n" + "-" * 60)
    if all_warnings:
        log("WARNINGS:")
        for w in all_warnings:
            log(f"  - {w}")

    if all_errors:
        log("ERRORS (must fix before proceeding):")
        for e in all_errors:
            log(f"  - {e}")
        log("\nPre-flight checks FAILED")
        return False

    log("Pre-flight checks PASSED")
    return True


def run_phase3_synthesis(limit: int = None) -> bool:
    """Run Phase 3: Generate CoT training data."""
    log("\n" + "=" * 60)
    log("PHASE 3: Synthesizing Contrastive Reasoning")
    log("=" * 60)

    start_time = time.time()

    # Check for existing progress
    existing_count = 0
    if COT_OUTPUT.exists():
        with open(COT_OUTPUT) as f:
            existing_count = sum(1 for _ in f)
        log(f"Found {existing_count} existing examples (will resume)")

    # Build command
    cmd = [sys.executable, str(PROJECT_ROOT / "scripts/synthesize_reasoning_cuda.py")]
    if limit:
        cmd.extend(["--limit", str(limit)])

    log(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)

        # Verify output
        if COT_OUTPUT.exists():
            with open(COT_OUTPUT) as f:
                final_count = sum(1 for _ in f)

            elapsed = time.time() - start_time
            log(f"Phase 3 complete: {final_count} examples in {elapsed/60:.1f} minutes")

            if final_count < MIN_TRAINING_EXAMPLES:
                log(f"WARNING: Only {final_count} examples (need {MIN_TRAINING_EXAMPLES} for training)")
                return False

            return True
        else:
            log("ERROR: Output file not created")
            return False

    except subprocess.CalledProcessError as e:
        log(f"ERROR: Phase 3 failed with exit code {e.returncode}")
        return False
    except Exception as e:
        log(f"ERROR: Phase 3 exception: {e}")
        return False


def run_phase4_training() -> bool:
    """Run Phase 4: Train LoRA adapter."""
    log("\n" + "=" * 60)
    log("PHASE 4: Training LoRA Adapter")
    log("=" * 60)

    start_time = time.time()

    # Verify training data exists
    if not COT_OUTPUT.exists():
        log("ERROR: Training data not found - run Phase 3 first")
        return False

    with open(COT_OUTPUT) as f:
        example_count = sum(1 for _ in f)
    log(f"Training data: {example_count} examples")

    # Check for existing checkpoints
    checkpoint_dirs = list(ADAPTER_OUTPUT.glob("checkpoint-*")) if ADAPTER_OUTPUT.exists() else []
    if checkpoint_dirs:
        latest = max(checkpoint_dirs, key=lambda p: int(p.name.split("-")[1]))
        log(f"Found checkpoint: {latest.name} (will auto-resume)")

    # Build command
    cmd = [sys.executable, str(PROJECT_ROOT / "scripts/train_lora_cuda.py")]

    log(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)

        # Verify output
        adapter_file = ADAPTER_OUTPUT / "adapter_model.safetensors"
        if adapter_file.exists():
            size_mb = adapter_file.stat().st_size / (1024 * 1024)
            elapsed = time.time() - start_time
            log(f"Phase 4 complete: adapter saved ({size_mb:.1f} MB) in {elapsed/60:.1f} minutes")
            return True
        else:
            # Check if there's a checkpoint we can use
            if checkpoint_dirs:
                log("WARNING: Final adapter not saved, but checkpoints exist")
                return True
            log("ERROR: No adapter or checkpoints created")
            return False

    except subprocess.CalledProcessError as e:
        log(f"ERROR: Phase 4 failed with exit code {e.returncode}")
        # Check if we at least have checkpoints
        checkpoint_dirs = list(ADAPTER_OUTPUT.glob("checkpoint-*")) if ADAPTER_OUTPUT.exists() else []
        if checkpoint_dirs:
            log(f"NOTE: {len(checkpoint_dirs)} checkpoints saved - can resume later")
        return False
    except Exception as e:
        log(f"ERROR: Phase 4 exception: {e}")
        return False


def run_phase5_benchmark() -> bool:
    """Run Phase 5: Benchmark the trained adapter."""
    log("\n" + "=" * 60)
    log("PHASE 5: Benchmarking Adapter")
    log("=" * 60)

    start_time = time.time()

    # Verify adapter exists
    adapter_file = ADAPTER_OUTPUT / "adapter_model.safetensors"
    if not adapter_file.exists():
        # Check checkpoints
        checkpoint_dirs = list(ADAPTER_OUTPUT.glob("checkpoint-*")) if ADAPTER_OUTPUT.exists() else []
        if checkpoint_dirs:
            latest = max(checkpoint_dirs, key=lambda p: int(p.name.split("-")[1]))
            log(f"Using checkpoint: {latest.name}")
        else:
            log("ERROR: No adapter found - run Phase 4 first")
            return False

    # Build command
    cmd = [sys.executable, str(PROJECT_ROOT / "scripts/benchmark_adapter.py")]

    log(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)

        # Check results file
        results_file = PROJECT_ROOT / "models/benchmark_results.json"
        if results_file.exists():
            with open(results_file) as f:
                results = json.load(f)

            elapsed = time.time() - start_time
            log(f"\nPhase 5 complete in {elapsed/60:.1f} minutes")
            log("-" * 40)
            log(f"Base Model Accuracy:  {results.get('base_accuracy', 0):.1f}%")
            log(f"CoT Adapter Accuracy: {results.get('cot_accuracy', 0):.1f}%")
            log(f"Improvement:          {results.get('cot_accuracy', 0) - results.get('base_accuracy', 0):+.1f}%")
            log("-" * 40)
            return True
        else:
            log("WARNING: Results file not created, but benchmark may have succeeded")
            return True

    except subprocess.CalledProcessError as e:
        log(f"ERROR: Phase 5 failed with exit code {e.returncode}")
        return False
    except Exception as e:
        log(f"ERROR: Phase 5 exception: {e}")
        return False


def run_quick_test() -> bool:
    """Run a quick test of the pipeline with 5 examples."""
    log("\n" + "=" * 60)
    log("QUICK TEST MODE (5 examples)")
    log("=" * 60)

    # Test Phase 3 with 5 examples
    log("\nTesting Phase 3 (synthesis)...")
    test_output = PROJECT_ROOT / "models/cot_dataset_test.jsonl"

    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts/synthesize_reasoning_cuda.py"),
        "--output", str(test_output),
        "--limit", "5",
        "--no-resume"
    ]

    try:
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, check=True, timeout=600)  # 10 min timeout

        if test_output.exists():
            with open(test_output) as f:
                count = sum(1 for _ in f)
            log(f"  Generated {count} test examples")

            # Clean up test file
            test_output.unlink()
            log("  Test file cleaned up")

            log("\nQuick test PASSED - ready for overnight run!")
            return True
        else:
            log("  ERROR: Test output not created")
            return False

    except subprocess.TimeoutExpired:
        log("  ERROR: Test timed out after 10 minutes")
        return False
    except subprocess.CalledProcessError as e:
        log(f"  ERROR: Test failed with exit code {e.returncode}")
        return False
    except Exception as e:
        log(f"  ERROR: Test exception: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Overnight Training Pipeline for cot_v4",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/run_overnight_training.py           # Full pipeline
    python scripts/run_overnight_training.py --test    # Quick test first
    python scripts/run_overnight_training.py --phase 4 # Start from Phase 4
    python scripts/run_overnight_training.py --preflight-only  # Just check readiness
        """
    )
    parser.add_argument("--test", action="store_true",
                        help="Run quick test (5 examples) before full run")
    parser.add_argument("--phase", type=int, choices=[3, 4, 5], default=3,
                        help="Start from specific phase (default: 3)")
    parser.add_argument("--preflight-only", action="store_true",
                        help="Only run pre-flight checks, don't train")
    parser.add_argument("--skip-preflight", action="store_true",
                        help="Skip pre-flight checks (use with caution)")
    args = parser.parse_args()

    # Initialize log
    log("\n" + "=" * 60)
    log("OVERNIGHT TRAINING PIPELINE - cot_v4")
    log(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)

    start_time = time.time()

    # Pre-flight checks
    if not args.skip_preflight:
        if not run_preflight_checks():
            log("\nAborting due to pre-flight check failures")
            sys.exit(1)

    if args.preflight_only:
        log("\nPre-flight only mode - exiting")
        sys.exit(0)

    # Quick test
    if args.test:
        if not run_quick_test():
            log("\nAborting due to quick test failure")
            sys.exit(1)
        else:
            log("\nQuick test passed! Ready for full overnight run.")
            log("To start the full pipeline, run without --test flag:")
            log("  python scripts/run_overnight_training.py")
            sys.exit(0)

    # Run phases
    success = True

    if args.phase <= 3:
        if not run_phase3_synthesis():
            log("\nPhase 3 failed - stopping pipeline")
            success = False

    if success and args.phase <= 4:
        if not run_phase4_training():
            log("\nPhase 4 failed - stopping pipeline")
            success = False

    if success and args.phase <= 5:
        if not run_phase5_benchmark():
            log("\nPhase 5 failed (non-critical)")
            # Don't set success=False - benchmark failure is non-critical

    # Summary
    elapsed = time.time() - start_time
    log("\n" + "=" * 60)
    log("PIPELINE COMPLETE")
    log("=" * 60)
    log(f"Total time: {elapsed/3600:.1f} hours ({elapsed/60:.0f} minutes)")

    if success:
        log("\nSUCCESS! Check models/adapters/cot_v4/ for the trained adapter")
        log("Run 'python scripts/benchmark_adapter.py' to see detailed results")
    else:
        log("\nPIPELINE FAILED - check log above for errors")
        log(f"Log file: {LOG_FILE}")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
