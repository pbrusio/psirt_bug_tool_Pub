"""
Local LLM Inference Module for PSIRT Labeling
Uses Foundation-Sec-8B via HuggingFace Transformers.
Supports CUDA (Linux) and CPU with LoRA adapter for improved accuracy.

For Mac/MPS: Use mlx_inference.py instead (MLX-optimized).
"""
import logging
import json
import re
import os
import torch
from pathlib import Path
from typing import List, Dict, Any, Optional
from fewshot_inference import FewShotPSIRTLabeler

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Model configuration
DEFAULT_MODEL = "fdtn-ai/Foundation-Sec-8B"

# Adapter paths - platform-specific LoRA weights
CUDA_ADAPTER_PATH = "models/adapters/cuda_v1"
MLX_ADAPTER_PATH = "models/adapters/mlx_v1"  # Note: MLX format, not loadable by PEFT


class TransformersPSIRTLabeler(FewShotPSIRTLabeler):
    """
    PSIRT Labeler using Foundation-Sec-8B via HuggingFace Transformers.
    Runs locally on Mac Studio with MPS (Apple Silicon GPU) acceleration.
    """
    
    def __init__(self, model_name: str = "foundation-sec-8b"):
        """
        Initialize the labeler with Foundation-Sec-8B model.
        
        Args:
            model_name: Model identifier (default uses Foundation-Sec-8B)
        """
        self.model_name = DEFAULT_MODEL
        self.model = None
        self.tokenizer = None
        self.device = None
        
        print("🚀 Initializing Foundation-Sec-8B PSIRT Labeler...")
        
        # Load the LLM model
        self._load_llm_model()
        
        self.taxonomy = {}
        # Load taxonomies
        self._load_taxonomy('taxonomies/features.yml', 'IOS-XE')
        self._load_taxonomy('taxonomies/features_iosxr.yml', 'IOS-XR')
        self._load_taxonomy('taxonomies/features_asa.yml', 'ASA')
        self._load_taxonomy('taxonomies/features_asa.yml', 'FTD')
        self._load_taxonomy('taxonomies/features_nxos.yml', 'NX-OS')
        
        # Populate 'Unknown' platform with ALL valid labels from other taxonomies
        all_labels = set()
        for labels in self.taxonomy.values():
            all_labels.update(labels)
        self.taxonomy['Unknown'] = list(all_labels)
        print(f"   ℹ️ 'Unknown' platform taxonomy populated with {len(all_labels)} unique labels")
        
        # Load FAISS index for retrieval
        self._load_embedder_and_index()
        
        print(f"✅ Foundation-Sec-8B Labeler ready on {self.device}")

    def _load_llm_model(self):
        """Load Foundation-Sec-8B model with optional LoRA adapter."""
        from transformers import AutoTokenizer, AutoModelForCausalLM

        print(f"📥 Loading model: {self.model_name}")
        print("   First run will download ~16GB. Subsequent runs use cache.")

        # Determine device
        if torch.backends.mps.is_available():
            self.device = torch.device("mps")
            print("   🍎 Using Apple MPS (Metal Performance Shaders)")
            print("   ⚠️  Note: For Mac, consider using mlx_inference.py for better performance")
        elif torch.cuda.is_available():
            self.device = torch.device("cuda")
            print("   🎮 Using NVIDIA CUDA")
        else:
            self.device = torch.device("cpu")
            print("   💻 Using CPU (slower)")

        # Load tokenizer
        print("   Loading tokenizer...")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)

        # Load model with appropriate settings
        print("   Loading model weights...")

        # MPS requires float32 to avoid NaN/Inf issues during generation
        # CUDA can use float16 for memory efficiency
        if self.device.type == "mps":
            print("   Using float16 for MPS (optimized)")
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16,
                low_cpu_mem_usage=True
            )
            self.model = self.model.to(self.device)
        elif self.device.type == "cuda":
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16,
                device_map="auto",
                low_cpu_mem_usage=True
            )
        else:
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float32,
                low_cpu_mem_usage=True
            )

        # Load LoRA adapter if available (CUDA/CPU only - PEFT format)
        self._load_adapter()

        self.model.eval()
        logger.info(f"✅ Model loaded successfully on {self.device}")

    def _load_adapter(self):
        """Load PEFT LoRA adapter if available for the current platform."""
        adapter_path = Path(CUDA_ADAPTER_PATH)

        # Skip adapter loading on MPS - use mlx_inference.py instead
        if self.device.type == "mps":
            print("   ℹ️  Skipping PEFT adapter on MPS (use mlx_inference.py for MLX adapter)")
            return

        # Check if adapter exists
        if not adapter_path.exists():
            print(f"   ⚠️  No adapter found at {adapter_path}")
            print("   Running with base model only (~20% accuracy)")
            return

        adapter_config = adapter_path / "adapter_config.json"
        adapter_weights = adapter_path / "adapter_model.safetensors"

        if not adapter_config.exists() or not adapter_weights.exists():
            print(f"   ⚠️  Incomplete adapter at {adapter_path}")
            print("   Running with base model only (~20% accuracy)")
            return

        try:
            from peft import PeftModel

            print(f"   📦 Loading LoRA adapter from {adapter_path}...")
            self.model = PeftModel.from_pretrained(
                self.model,
                str(adapter_path),
                is_trainable=False
            )
            print("   ✅ LoRA adapter loaded (~57% accuracy)")

        except ImportError:
            print("   ⚠️  PEFT not installed. Run: pip install peft")
            print("   Running with base model only (~20% accuracy)")
        except Exception as e:
            logger.warning(f"Failed to load adapter: {e}")
            print(f"   ⚠️  Adapter loading failed: {e}")
            print("   Running with base model only (~20% accuracy)")

    def load_model(self):
        """Override - model is loaded in __init__ via _load_llm_model()"""
        pass

    def generate_response(self, prompt: str) -> str:
        """
        Generate response using Foundation-Sec-8B via Transformers.
        
        Args:
            prompt: The full prompt with few-shot examples
            
        Returns:
            Raw text response from the model
        """
        try:
            logger.info(f"Generating with Foundation-Sec-8B on {self.device}...")
            
            # Tokenize input
            inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=4096)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Generate response
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs["input_ids"],
                    attention_mask=inputs.get("attention_mask"),
                    max_new_tokens=128,
                    do_sample=True,
                    temperature=0.1,
                    top_p=0.9,
                    pad_token_id=self.tokenizer.eos_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )
            
            # Decode response (only the new tokens)
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Remove the prompt from response to get just the generated part
            response = response[len(prompt):].strip()
            
            return response
            
        except Exception as e:
            logger.error(f"Inference failed: {e}")
            return "[]"

    def parse_output(self, response_text: str, platform: str) -> List[str]:
        """
        Parse LLM response to extract labels.
        
        Args:
            response_text: Raw response from the model
            platform: Platform to validate labels against
            
        Returns:
            List of validated labels
        """
        predicted_labels = []
        
        try:
            # Method 1: Look for complete JSON with "labels" array
            json_match = re.search(r'\{\s*"labels"\s*:\s*\[([^\]]*)\]\s*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    predicted_labels = result.get('labels', [])
                except:
                    pass

            # Method 2: Extract labels array directly (even if incomplete)
            if not predicted_labels:
                labels_match = re.search(r'"labels"\s*:\s*\[([^\]]*)', response_text, re.DOTALL)
                if labels_match:
                    labels_str = labels_match.group(1)
                    label_items = re.findall(r'"([^"]+)"', labels_str)
                    predicted_labels = label_items[:3]

            # Method 3: Standard JSON parsing
            if not predicted_labels:
                first_brace = response_text.find('{')
                last_brace = response_text.rfind('}')
                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    json_candidate = response_text[first_brace:last_brace+1]
                    result = json.loads(json_candidate)
                    predicted_labels = result.get('labels', [])

        except Exception as e:
            logger.warning(f"Label parsing warning: {e}")
            # Last resort: look for label-like patterns
            potential_labels = re.findall(r'"([A-Z_][A-Za-z0-9_]+)"', response_text)
            predicted_labels = [l for l in potential_labels if '_' in l][:3]

        # Validate against taxonomy
        valid_labels = self.taxonomy.get(platform, [])
        validated_labels = [l for l in predicted_labels if l in valid_labels]
        
        return validated_labels

    def predict_labels(self, summary: str, platform: str, advisory_id: str = None) -> Dict[str, Any]:
        """
        Predict labels for a PSIRT summary using Foundation-Sec-8B.
        """
        # 1. Check for exact match first (if advisory_id provided)
        if advisory_id:
            exact_match = self.exact_match_lookup(advisory_id, platform=platform)
            if exact_match:
                logger.info(f"✅ EXACT MATCH: Found {advisory_id} in training data")
                return {
                    'psirt_summary': summary,
                    'platform': platform,
                    'advisory_id': advisory_id,
                    'predicted_labels': exact_match['labels'],
                    'confidence': 1.0,
                    'source': 'exact_match',
                    'retrieved_examples': [],
                    'raw_response': f"Exact match from {exact_match.get('source', 'training_data')}"
                }
        
        # 2. Retrieve similar examples
        examples, similarity_scores = self.retrieve_similar_examples(summary, platform, k=5)
        
        # Calculate confidence from similarity
        confidence = sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0.0
        
        # 3. Build Prompt (use parent's build_fewshot_prompt)
        prompt = self.build_fewshot_prompt(summary, platform, examples)
        
        # 4. Generate with Foundation-Sec-8B
        response_text = self.generate_response(prompt)
        
        # 5. Parse and validate labels
        predicted_labels = self.parse_output(response_text, platform)
        
        return {
            'psirt_summary': summary,
            'platform': platform,
            'advisory_id': advisory_id,
            'predicted_labels': predicted_labels,
            'confidence': confidence,
            'source': 'transformers_few_shot',
            'retrieved_examples': examples,
            'raw_response': response_text
        }


# Backward compatibility alias
OllamaPSIRTLabeler = TransformersPSIRTLabeler


if __name__ == "__main__":
    # Test run
    labeler = TransformersPSIRTLabeler()
    test_summary = "A vulnerability in the web UI of Cisco IOS XE Software could allow an unauthenticated remote attacker to cause a denial of service."
    result = labeler.predict_labels(test_summary, "IOS-XE")
    print("\nPredicted Labels:", result['predicted_labels'])









