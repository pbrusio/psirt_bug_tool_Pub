"""
Comprehensive CoT Adapter Evaluation
Compares base Foundation-Sec-8B vs CoT-trained adapter
"""
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import time
import json

BASE_MODEL = "fdtn-ai/Foundation-Sec-8B"
ADAPTER_PATH = "models/adapters/cot_v1"

# Test cases with known expected labels (from training data)
TEST_CASES = [
    {
        "id": "CSRF_WebUI",
        "summary": "A vulnerability in the web-based management interface of Cisco IP Phone Firmware could allow an unauthenticated, remote attacker to conduct a cross-site request forgery (CSRF) attack on an affected device. The vulnerability is due to insufficient CSRF protections for the web-based management interface.",
        "platform": "IOS-XE",
        "expected_labels": ["MGMT_SSH_HTTP"],
    },
    {
        "id": "BGP_DoS",
        "summary": "A vulnerability in the Border Gateway Protocol (BGP) implementation of Cisco IOS XE Software could allow an unauthenticated, remote attacker to cause a denial of service (DoS) condition. The vulnerability is due to improper processing of BGP update messages.",
        "platform": "IOS-XE",
        "expected_labels": ["RTE_BGP"],
    },
    {
        "id": "SSH_Auth_Bypass",
        "summary": "A vulnerability in the SSH server implementation of Cisco IOS XE Software could allow an authenticated, remote attacker to bypass authentication. The vulnerability exists because the SSH implementation does not properly validate user credentials.",
        "platform": "IOS-XE",
        "expected_labels": ["MGMT_SSH_HTTP", "MGMT_AAA_TACACS_RADIUS"],
    },
    {
        "id": "OSPF_Overflow",
        "summary": "A vulnerability in the OSPF routing protocol implementation of Cisco IOS XE could allow an unauthenticated attacker to cause a buffer overflow. The vulnerability is due to insufficient bounds checking in OSPF LSA processing.",
        "platform": "IOS-XE",
        "expected_labels": ["RTE_OSPF"],
    },
    {
        "id": "ACL_Bypass",
        "summary": "A vulnerability in the access control list (ACL) processing of Cisco IOS XE Software could allow an unauthenticated, remote attacker to bypass configured ACLs. The vulnerability is due to improper handling of ACL rules.",
        "platform": "IOS-XE",
        "expected_labels": ["SEC_ACL"],
    },
]

def build_prompt(summary: str) -> str:
    return f"""### Instruction:
Classify the following Cisco Security Advisory into the correct technical feature label.

### Input:
{summary}

### Response:
"""

def run_inference(model, tokenizer, prompt: str, device) -> tuple:
    """Run inference and return (output_text, time_taken)"""
    inputs = tokenizer(prompt, return_tensors="pt").to(device)

    start = time.time()
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=250,
            temperature=0.1,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    elapsed = time.time() - start

    full_output = tokenizer.decode(outputs[0], skip_special_tokens=True)
    response = full_output.split("### Response:")[-1].strip()
    return response, elapsed

def extract_labels(text: str) -> list:
    """Extract labels from model output"""
    import re
    # Look for labels in various formats
    labels = []

    # Format 1: Label: ['X', 'Y']
    match = re.search(r"Label[s]?:\s*\[([^\]]+)\]", text, re.IGNORECASE)
    if match:
        labels = re.findall(r"'([^']+)'", match.group(1))
        if not labels:
            labels = re.findall(r'"([^"]+)"', match.group(1))

    # Format 2: {"labels": ["X", "Y"]}
    if not labels:
        match = re.search(r'"labels"\s*:\s*\[([^\]]+)\]', text)
        if match:
            labels = re.findall(r'"([^"]+)"', match.group(1))

    # Format 3: Just find label-like patterns (UPPERCASE_WITH_UNDERSCORES)
    if not labels:
        potential = re.findall(r'\b([A-Z][A-Z0-9_]+(?:_[A-Z0-9]+)+)\b', text)
        labels = [l for l in potential if len(l) > 5][:3]

    return labels

def has_reasoning(text: str) -> bool:
    """Check if output contains reasoning/explanation"""
    reasoning_indicators = [
        "reasoning", "because", "suggests", "indicates", "related to",
        "this means", "therefore", "the vulnerability", "based on",
        "1.", "2.", "3.",  # Numbered reasoning steps
        "first", "second", "finally"
    ]
    text_lower = text.lower()
    return any(ind in text_lower for ind in reasoning_indicators)

def main():
    print("=" * 70)
    print("CoT ADAPTER EVALUATION: Base Model vs Fine-tuned Adapter")
    print("=" * 70)

    # Determine device
    if torch.backends.mps.is_available():
        device = torch.device("mps")
        print(f"\n🍎 Using Apple MPS")
    elif torch.cuda.is_available():
        device = torch.device("cuda")
        print(f"\n🎮 Using CUDA")
    else:
        device = torch.device("cpu")
        print(f"\n💻 Using CPU")

    # Load tokenizer
    print(f"\n📥 Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    # Load base model
    print(f"📥 Loading base model: {BASE_MODEL}")
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16,
        device_map="auto"
    )
    base_model.eval()

    # Run base model tests
    print("\n" + "=" * 70)
    print("PHASE 1: BASE MODEL (No Adapter)")
    print("=" * 70)

    base_results = []
    for tc in TEST_CASES:
        print(f"\n🔍 Test: {tc['id']}")
        prompt = build_prompt(tc['summary'])
        output, elapsed = run_inference(base_model, tokenizer, prompt, device)
        labels = extract_labels(output)
        has_reason = has_reasoning(output)

        # Check accuracy
        expected = set(tc['expected_labels'])
        predicted = set(labels)
        correct = len(expected & predicted) > 0

        base_results.append({
            'id': tc['id'],
            'labels': labels,
            'has_reasoning': has_reason,
            'correct': correct,
            'time': elapsed,
            'output': output[:300]
        })

        print(f"   Labels: {labels}")
        print(f"   Expected: {tc['expected_labels']}")
        print(f"   Correct: {'✅' if correct else '❌'}")
        print(f"   Has Reasoning: {'✅' if has_reason else '❌'}")
        print(f"   Time: {elapsed:.2f}s")

    # Load adapter
    print("\n" + "=" * 70)
    print("PHASE 2: WITH CoT ADAPTER")
    print("=" * 70)

    print(f"\n🔗 Loading adapter: {ADAPTER_PATH}")
    adapter_model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
    adapter_model.eval()

    adapter_results = []
    for tc in TEST_CASES:
        print(f"\n🔍 Test: {tc['id']}")
        prompt = build_prompt(tc['summary'])
        output, elapsed = run_inference(adapter_model, tokenizer, prompt, device)
        labels = extract_labels(output)
        has_reason = has_reasoning(output)

        # Check accuracy
        expected = set(tc['expected_labels'])
        predicted = set(labels)
        correct = len(expected & predicted) > 0

        adapter_results.append({
            'id': tc['id'],
            'labels': labels,
            'has_reasoning': has_reason,
            'correct': correct,
            'time': elapsed,
            'output': output[:300]
        })

        print(f"   Labels: {labels}")
        print(f"   Expected: {tc['expected_labels']}")
        print(f"   Correct: {'✅' if correct else '❌'}")
        print(f"   Has Reasoning: {'✅' if has_reason else '❌'}")
        print(f"   Time: {elapsed:.2f}s")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY COMPARISON")
    print("=" * 70)

    base_correct = sum(1 for r in base_results if r['correct'])
    base_reasoning = sum(1 for r in base_results if r['has_reasoning'])
    base_avg_time = sum(r['time'] for r in base_results) / len(base_results)

    adapter_correct = sum(1 for r in adapter_results if r['correct'])
    adapter_reasoning = sum(1 for r in adapter_results if r['has_reasoning'])
    adapter_avg_time = sum(r['time'] for r in adapter_results) / len(adapter_results)

    print(f"\n{'Metric':<25} {'Base Model':<15} {'With Adapter':<15} {'Delta':<10}")
    print("-" * 65)
    print(f"{'Label Accuracy':<25} {base_correct}/{len(TEST_CASES):<15} {adapter_correct}/{len(TEST_CASES):<15} {'+' if adapter_correct >= base_correct else ''}{adapter_correct - base_correct}")
    print(f"{'Has Reasoning':<25} {base_reasoning}/{len(TEST_CASES):<15} {adapter_reasoning}/{len(TEST_CASES):<15} {'+' if adapter_reasoning >= base_reasoning else ''}{adapter_reasoning - base_reasoning}")
    print(f"{'Avg Inference Time':<25} {base_avg_time:.2f}s{'':<10} {adapter_avg_time:.2f}s{'':<10} {'+' if adapter_avg_time > base_avg_time else ''}{adapter_avg_time - base_avg_time:.2f}s")

    print("\n" + "=" * 70)
    print("DETAILED OUTPUT COMPARISON (First Test Case)")
    print("=" * 70)
    print(f"\n📋 BASE MODEL OUTPUT:\n{base_results[0]['output']}...")
    print(f"\n📋 ADAPTER OUTPUT:\n{adapter_results[0]['output']}...")

    # Save results
    results = {
        'base_model': base_results,
        'adapter_model': adapter_results,
        'summary': {
            'base_accuracy': base_correct / len(TEST_CASES),
            'adapter_accuracy': adapter_correct / len(TEST_CASES),
            'base_reasoning_rate': base_reasoning / len(TEST_CASES),
            'adapter_reasoning_rate': adapter_reasoning / len(TEST_CASES),
        }
    }

    with open('scripts/cot_eval_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Results saved to scripts/cot_eval_results.json")

if __name__ == "__main__":
    main()
