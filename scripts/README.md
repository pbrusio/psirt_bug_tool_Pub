# Scripts Directory

Utility scripts for training, evaluation, data processing, and system maintenance.

## Active Scripts

### Training & Evaluation
| Script | Purpose |
|--------|---------|
| `evaluate_lora_comprehensive.py` | Full LoRA adapter evaluation (v3, v4a, v4b) |
| `train_lora_cuda.py` | CUDA-based LoRA training |
| `benchmark_adapter.py` | Adapter performance benchmarking |
| `benchmark_cot.py` | Chain-of-Thought evaluation |
| `test_cot_adapter.py` | Quick adapter smoke tests |
| `test_cot_comparison.py` | Compare CoT vs non-CoT |

### Data Processing
| Script | Purpose |
|--------|---------|
| `prepare_cot_dataset.py` | Prepare training data for MLX-LM |
| `prepare_training_data.py` | General training data preparation |
| `prune_data_for_training.py` | Clean and filter training data |
| `standardize_labels.py` | Normalize label format |
| `build_faiss_index.py` | Rebuild FAISS vector index |

### CoT Synthesis
| Script | Purpose |
|--------|---------|
| `synthesize_reasoning_openai.py` | Generate CoT with OpenAI GPT-4o |
| `synthesize_reasoning_gemini.py` | Generate CoT with Gemini |
| `synthesize_reasoning_cuda.py` | GPU-based synthesis |
| `synthesize_reasoning.py` | Base synthesis script |

### Taxonomy & Labels
| Script | Purpose |
|--------|---------|
| `enrich_taxonomy_definitions.py` | Add semantic definitions to taxonomy |
| `merge_taxonomy_updates.py` | Merge taxonomy updates |
| `ingest_frontier_labels.py` | Ingest frontier taxonomy batches |

### Database & Bugs
| Script | Purpose |
|--------|---------|
| `cisco_vuln_fetcher.py` | Fetch Cisco vulnerability data |
| `enrich_bugs.py` | Enrich bug records |
| `close_loop.py` | Self-training loop closure |
| `self_train.py` | Self-training pipeline |

### Maintenance
| Script | Purpose |
|--------|---------|
| `cleanup_duplicate_devices.py` | Remove duplicate device entries |
| `verify_ingestion.py` | Verify data ingestion |
| `curate_gold_eval.py` | Curate gold evaluation set |

## Directory Structure

### `demos/`
Demo scripts showing database scanning and feature-aware filtering
- `demo_scan.py` - Basic vulnerability scanning demo
- `demo_scan_simple.py` - Simplified version-only scanning
- `demo_scan_feature_aware.py` - Feature-aware filtering demo (40-80% false positive reduction)

**Usage:**
```bash
python scripts/demos/demo_scan_feature_aware.py
```

### `migrations/`
Database migration scripts for schema updates
- `migration_add_hardware_model.py` - Add hardware_model column to vulnerabilities table
- `backfill_hardware_models.py` - Extract and populate hardware models from bug summaries

**Usage:**
```bash
# Run migrations (already applied to production DB)
python scripts/migrations/migration_add_hardware_model.py
python scripts/migrations/backfill_hardware_models.py
```

### `tests/`
Standalone test scripts for specific features
- `test_hardware_filtering.py` - Hardware model filtering validation (6 scenarios)
- `test_hardware_db.py` - Hardware database queries and performance
- `test_hardware_autodetect.py` - Hardware extraction from "show version" (7 tests)
- `test_psirt_cache.py` - Three-tier PSIRT caching validation
- `test_comprehensive_system.py` - End-to-end system tests
- `test_device_verification.py` - Live SSH device verification
- `test_faiss_improvement.py` - FAISS index performance validation

**Usage:**
```bash
# Run specific test
python scripts/tests/test_hardware_filtering.py

# Run all tests via pytest
cd .. && pytest tests/
```

## Frontier Batch Files

YAML configurations for taxonomy batch updates:
- `frontier_batch_*.yaml` - Taxonomy batches by domain (L2, L3, security, management, etc.)

## Shell Scripts

Utility shell scripts in root `scripts/` folder:
- `run_finetuning.sh` - Llama fine-tuning pipeline (deprecated)
- `run_gemini_test.sh` - Gemini API labeling test (deprecated)
- `run_pipeline.sh` - Legacy PSIRT pipeline (deprecated)
- `setup_venv.sh` - Virtual environment setup
- `test_snapshot_api.sh` - Test snapshot verification API
- `test_snapshot_verification.sh` - Test air-gapped snapshot workflow

## Usage Examples

### Run LoRA Evaluation
```bash
source venv_mac/bin/activate
python scripts/evaluate_lora_comprehensive.py --all
```

### Rebuild FAISS Index
```bash
python scripts/build_faiss_index.py
```

### Synthesize CoT Reasoning
```bash
python scripts/synthesize_reasoning_openai.py --input data.jsonl --output cot_data.jsonl
```

## Running Tests

```bash
# Unit tests (via pytest)
pytest tests/

# Integration tests (standalone scripts)
python scripts/tests/test_comprehensive_system.py

# Hardware filtering validation
python scripts/tests/test_hardware_filtering.py
```

## Production Testing

For production API testing, use:
- **Web UI:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs
- **Demo Scripts:** `scripts/demos/` for quick CLI testing
