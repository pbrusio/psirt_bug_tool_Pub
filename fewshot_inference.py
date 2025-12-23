#!/usr/bin/env python3
"""
Few-shot inference pipeline with Foundation-Sec-8B and retrieval-augmented generation
"""
from transformers import AutoModelForCausalLM, AutoTokenizer
from sentence_transformers import SentenceTransformer
import faiss
import pandas as pd
import torch
import json
import yaml
import re
import platform

class FewShotPSIRTLabeler:
    def __init__(self):
        print("🚀 Initializing Few-Shot PSIRT Labeler...")

        # Load Foundation-Sec-8B model
        print("\n📥 Loading Foundation-Sec-8B model...")
        model_id = "fdtn-ai/Foundation-Sec-8B"

        # Use different loading strategies based on platform
        if platform.system() == "Darwin":
            # Mac: Use float32 with MPS (float16 causes inf/nan errors)
            print("   🍎 Using float32 on Apple Silicon (MPS)")
            self.tokenizer = AutoTokenizer.from_pretrained(model_id)
            self.model = AutoModelForCausalLM.from_pretrained(
                model_id,
                torch_dtype=torch.float32,
                low_cpu_mem_usage=True
            )
            # Move to MPS if available
            if torch.backends.mps.is_available():
                self.model = self.model.to("mps")
        else:
            # Linux/Windows: Use 8-bit quantization with bitsandbytes
            print("   💻 Using 8-bit quantization with bitsandbytes")
            from transformers import BitsAndBytesConfig
            quantization_config = BitsAndBytesConfig(
                load_in_8bit=True,
                llm_int8_threshold=6.0
            )
            self.tokenizer = AutoTokenizer.from_pretrained(model_id)
            self.model = AutoModelForCausalLM.from_pretrained(
                model_id,
                quantization_config=quantization_config,
                device_map="auto"
            )
        
        # Load CoT Adapter if it exists
        try:
            from peft import PeftModel
            adapter_path = "models/adapters/cot_v1"
            print(f"   🔗 Loading CoT Adapter from {adapter_path}...")
            self.model = PeftModel.from_pretrained(self.model, adapter_path)
            print("   ✅ CoT Adapter loaded successfully")
        except Exception as e:
            print(f"   ⚠️ Could not load adapter (Running with Base Model): {e}")

        print("✅ Model loaded")

        # Load sentence embedder and FAISS index
        self._load_embedder_and_index()

    def _load_embedder_and_index(self):
        """Load sentence embedder and FAISS index"""
        print("\n📚 Loading sentence embedder...")
        with open('models/embedder_info.json', 'r') as f:
            embedder_info = json.load(f)
        self.embedder = SentenceTransformer(embedder_info['model_name'])
        print("✅ Embedder loaded")

        print("\n🔍 Loading FAISS index...")
        self.index = faiss.read_index('models/faiss_index.bin')
        self.labeled_examples = pd.read_parquet('models/labeled_examples.parquet')
        print(f"✅ Index loaded ({self.index.ntotal} examples)")

        # Load taxonomy
        print("\n📖 Loading feature taxonomies...")
        self.taxonomy = {}
        self._load_taxonomy('taxonomies/features.yml', 'IOS-XE')
        self._load_taxonomy('taxonomies/features_iosxr.yml', 'IOS-XR')
        self._load_taxonomy('taxonomies/features_asa.yml', 'ASA')
        self._load_taxonomy('taxonomies/features_asa.yml', 'FTD')  # FTD uses ASA taxonomy
        self._load_taxonomy('taxonomies/features_nxos.yml', 'NX-OS')

        total_labels = sum(len(labels) for labels in self.taxonomy.values())
        print(f"✅ Taxonomies loaded ({len(self.taxonomy)} platforms, {total_labels} total labels)")

    def _load_taxonomy(self, filepath, platform):
        """Load taxonomy YAML and extract labels for platform"""
        try:
            with open(filepath, 'r') as f:
                features = yaml.safe_load(f)
            self.taxonomy[platform] = [f['label'] for f in features]
        except FileNotFoundError:
            print(f"⚠️  Warning: {filepath} not found, skipping {platform}")
            self.taxonomy[platform] = []

    def exact_match_lookup(self, advisory_id, platform=None):
        """
        Lookup labels by exact advisory_id match in training data

        Args:
            advisory_id: Advisory ID (e.g., "cisco-sa-iosxe-ssh-dos")
            platform: Optional platform filter

        Returns:
            dict or None: {
                'labels': [...],
                'summary': '...',
                'platform': '...'
            }
        """
        if not advisory_id:
            return None

        # Check for advisory_id column (may be 'id' or 'advisoryId' depending on data source)
        id_column = 'advisoryId' if 'advisoryId' in self.labeled_examples.columns else 'id'
        matches = self.labeled_examples[self.labeled_examples[id_column] == advisory_id]

        if platform:
            matches = matches[matches['platform'] == platform]

        if len(matches) == 0:
            return None

        # Return first match (should only be one per platform)
        row = matches.iloc[0]
        labels = row['labels_list']
        if hasattr(labels, 'tolist'):
            labels = labels.tolist()

        return {
            'labels': labels,
            'summary': row['summary'],
            'platform': row['platform'],
            'source': row.get('source', 'training_data')
        }

    def retrieve_similar_examples(self, query_text, platform=None, k=5):
        """Retrieve k most similar labeled examples from FAISS index

        Returns:
            tuple: (examples, similarity_scores)
                - examples: list of retrieved example dicts
                - similarity_scores: list of similarity scores (0-1, higher is better)
        """
        # Embed query
        query_embedding = self.embedder.encode([query_text])

        # Search for more candidates than needed (filter by platform later)
        distances, indices = self.index.search(query_embedding.astype('float32'), k=min(k*3, self.index.ntotal))

        # Convert L2 distances to similarity scores (0-1, where 1 is most similar)
        # FAISS returns squared L2 distances, so we normalize them
        # similarity = 1 / (1 + distance)
        similarities = 1 / (1 + distances[0])

        # Filter by platform if specified
        examples = []
        similarity_scores = []
        for idx, similarity in zip(indices[0], similarities):
            row = self.labeled_examples.iloc[idx]
            if platform and row['platform'] != platform:
                continue

            # Convert labels to list if it's a numpy array
            labels = row['labels_list']
            if hasattr(labels, 'tolist'):
                labels = labels.tolist()

            examples.append({
                'summary': row['summary'],
                'platform': row['platform'],
                'labels': labels,
                'reasoning': row.get('reasoning', None)
            })
            similarity_scores.append(float(similarity))
            if len(examples) >= k:
                break

        return examples, similarity_scores

    def build_fewshot_prompt(self, psirt_summary, platform, examples):
        """Build few-shot prompt with retrieved examples"""
        valid_labels = self.taxonomy.get(platform, [])
        prompt = f"""You are a Cisco security advisory labeling expert. Your task is to assign feature labels from a closed taxonomy to PSIRTs based on their summary text.

Platform: {platform}

CRITICAL: You must ONLY use labels from this exact list. Do not invent new labels.
Available labels for {platform}:
{', '.join(sorted(valid_labels))}

Here are some examples of correctly labeled PSIRTs:

"""
        # Add retrieved examples
        for i, ex in enumerate(examples, 1):
            prompt += f"""Example {i}:
Summary: {ex['summary']}
Platform: {ex['platform']}
"""
            if ex.get('reasoning'):
                prompt += f"Reasoning: {ex['reasoning']}\n"
            
            prompt += f"Labels: {json.dumps(ex['labels'])}\n\n"""

        prompt += f"""Now label this new PSIRT.

CRITICAL: Return a valid JSON object with two fields:
1. "reasoning": A single sentence explaining why the labels match the summary.
2. "labels": A list of up to 3 valid labels from the taxonomy above.

Format:
{{
  "reasoning": "The summary mentions X, which indicates Y feature is affected.",
  "labels": ["LABEL1", "LABEL2"]
}}

Summary: {psirt_summary}
Platform: {platform}

JSON:"""

        return prompt

    def predict_labels(self, psirt_summary, platform, advisory_id=None, k=5, max_new_tokens=300):
        """Predict labels for a PSIRT using exact match or few-shot learning

        Process:
        1. If advisory_id provided, check for exact match in training data → 100% confidence
        2. If no exact match, use FAISS few-shot retrieval → similarity-based confidence

        Args:
            psirt_summary: PSIRT summary text
            platform: Platform (IOS-XE, IOS-XR, ASA, FTD, NX-OS)
            advisory_id: Optional advisory ID for exact matching
            k: Number of similar examples to retrieve (for few-shot)
            max_new_tokens: Max tokens for SEC-8B generation

        Returns:
            dict: {
                'predicted_labels': list of labels,
                'confidence': float 0-1,
                'source': 'exact_match' | 'few_shot',
                ...
            }
        """
        # STEP 1: Try exact match first (if advisory_id provided)
        if advisory_id:
            exact_match = self.exact_match_lookup(advisory_id, platform=platform)
            if exact_match:
                print(f"✅ EXACT MATCH: Found {advisory_id} in training data")
                print(f"   Labels: {exact_match['labels']}")
                return {
                    'predicted_labels': exact_match['labels'],
                    'reasoning': f"Exact match from training data ({exact_match['source']})",
                    'confidence': 1.0,  # 100% confidence for exact matches
                    'source': 'exact_match',
                    'match_type': 'training_data',
                    'raw_response': f"Exact match from {exact_match['source']}",
                    'retrieved_examples': [],
                    'similarity_scores': [1.0]
                }

        # STEP 2: No exact match - use FAISS few-shot retrieval
        print(f"🔍 No exact match - using FAISS few-shot retrieval")

        # Retrieve similar examples with similarity scores
        examples, similarity_scores = self.retrieve_similar_examples(psirt_summary, platform=platform, k=k)

        if not examples:
            print(f"⚠️  Warning: No examples found for platform {platform}, using generic examples")
            examples, similarity_scores = self.retrieve_similar_examples(psirt_summary, platform=None, k=k)

        # Calculate confidence score from average similarity
        confidence = sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0.0


        # Build prompt
        prompt = self.build_fewshot_prompt(psirt_summary, platform, examples)

        # Generate
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=0.2,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id
            )

        # Decode response
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Extract JSON from response with aggressive multi-method parsing
        predicted_labels = []
        reasoning = ""
        json_text = ""

        try:
            # Extract everything after the prompt
            json_start = response.rfind("JSON:")
            if json_start != -1:
                json_text = response[json_start + len("JSON:"):].strip()
            else:
                json_text = response.split(prompt)[-1].strip()

            # Method 1: Look for complete JSON with "reasoning" and "labels"
            json_match = re.search(r'\{[^{}]*"reasoning"[^{}]*"labels"[^{}]*\[([^\]]*)\][^{}]*\}', json_text, re.DOTALL)
            if not json_match:
                # Try alternate order: labels first, then reasoning
                json_match = re.search(r'\{[^{}]*"labels"[^{}]*\[([^\]]*)\][^{}]*"reasoning"[^{}]*\}', json_text, re.DOTALL)

            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    predicted_labels = result.get('labels', [])
                    reasoning = result.get('reasoning', '')
                except:
                    pass

            # Method 2: Parse reasoning and labels separately if Method 1 failed
            if not predicted_labels:
                # Extract reasoning
                reasoning_match = re.search(r'"reasoning"\s*:\s*"([^"]*)"', json_text, re.DOTALL)
                if reasoning_match:
                    reasoning = reasoning_match.group(1)

                # Extract labels array
                labels_match = re.search(r'"labels"\s*:\s*\[([^\]]*)', json_text, re.DOTALL)
                if labels_match:
                    labels_str = labels_match.group(1)
                    label_items = re.findall(r'"([^"]+)"', labels_str)
                    predicted_labels = label_items[:3]

            # Method 3: Try standard JSON parsing
            if not predicted_labels:
                first_brace = json_text.find('{')
                last_brace = json_text.rfind('}')
                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    json_candidate = json_text[first_brace:last_brace+1]
                    result = json.loads(json_candidate)
                    predicted_labels = result.get('labels', [])
                    if not reasoning:
                        reasoning = result.get('reasoning', '')

        except Exception as e:
            # Silent fail - we've already extracted what we could
            if not predicted_labels:
                # Last resort: look for any label-like patterns in quotes
                potential_labels = re.findall(r'"([A-Z_][A-Za-z0-9_]+)"', json_text)
                predicted_labels = [l for l in potential_labels if '_' in l][:3]

        # Validate against taxonomy
        valid_labels = self.taxonomy.get(platform, [])
        validated_labels = [l for l in predicted_labels if l in valid_labels]

        return {
            'predicted_labels': validated_labels,
            'reasoning': reasoning,
            'confidence': confidence,
            'source': 'few_shot',
            'raw_response': response,
            'retrieved_examples': examples,
            'similarity_scores': similarity_scores
        }

# Main execution
if __name__ == "__main__":
    # Initialize labeler
    labeler = FewShotPSIRTLabeler()

    # Test cases
    test_cases = [
        {
            'summary': 'A vulnerability in the SSH server of Cisco IOS XE Software could allow an unauthenticated remote attacker to cause a denial of service condition',
            'platform': 'IOS-XE'
        },
        {
            'summary': 'VPN IPSec tunnel establishment fails when using IKEv2 with certificate authentication on ASA',
            'platform': 'ASA'
        },
        {
            'summary': 'SNMP community string exposure in configuration backup files',
            'platform': 'IOS-XE'
        }
    ]

    print("\n" + "="*80)
    print("🧪 Running test predictions...")
    print("="*80)

    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"Test Case {i}:")
        print(f"Summary: {test['summary']}")
        print(f"Platform: {test['platform']}")
        print(f"{'='*80}")

        result = labeler.predict_labels(test['summary'], test['platform'])

        print(f"\n✅ Predicted Labels: {result['predicted_labels']}")
        print(f"\n📚 Retrieved Examples:")
        for j, ex in enumerate(result['retrieved_examples'][:3], 1):
            print(f"  {j}. [{ex['platform']}] {ex['summary'][:60]}...")
            print(f"     Labels: {ex['labels']}")

    print(f"\n{'='*80}")
    print("✅ Testing complete!")
    print(f"{'='*80}")
