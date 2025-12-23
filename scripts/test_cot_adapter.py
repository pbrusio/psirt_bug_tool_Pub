import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import time

BASE_MODEL = "fdtn-ai/Foundation-Sec-8B"
ADAPTER_PATH = "models/adapters/cot_v1"

def test_inference():
    print(f"🍎 Loading Base Model: {BASE_MODEL} (MPS/Float16)...")
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16,
        device_map="auto" # Should pick MPS
    )
    
    print(f"🔗 Loading Adapter: {ADAPTER_PATH}...")
    try:
        model = PeftModel.from_pretrained(model, ADAPTER_PATH)
        print("✅ Adapter loaded successfully.")
    except Exception as e:
        print(f"❌ Failed to load adapter: {e}")
        return

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    
    # Test Input (A real advisory summary)
    test_summary = "A vulnerability in the web-based management interface of Cisco IP Phone Firmware could allow an unauthenticated, remote attacker to conduct a cross-site request forgery (CSRF) attack on an affected device. The vulnerability is due to insufficient CSRF protections for the web-based management interface."
    
    prompt = f"""### Instruction:
Classify the following Cisco Security Advisory into the correct technical feature label.

### Input:
{test_summary}

### Response:
"""

    print("\n📝 Test Prompt:")
    print(prompt)
    
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    
    print("\n🚀 Generating Response...")
    start_time = time.time()
    with torch.no_grad():
        outputs = model.generate(
            **inputs, 
            max_new_tokens=200, 
            temperature=0.1, # Low temp for deterministic test
            do_sample=False
        )
    end_time = time.time()
    
    full_output = tokenizer.decode(outputs[0], skip_special_tokens=True)
    generated_text = full_output.split("### Response:")[-1].strip()
    
    print("-" * 40)
    print("🤖 Model Output:")
    print(generated_text)
    print("-" * 40)
    print(f"Time: {end_time - start_time:.2f}s")
    
    if "Reasoning:" in generated_text and "Label:" in generated_text:
        print("\n✅ Verification PASSED: Output contains both Reasoning and Label.")
    else:
        print("\n❌ Verification FAILED: Output missing expected structure.")

if __name__ == "__main__":
    test_inference()
