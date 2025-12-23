import pandas as pd
import json
import os

INPUT_FILE = "models/labeled_examples_cleaned.parquet"
OUTPUT_DIR = "llama_training_data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "cot_dataset.jsonl")

def prepare_data():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    print(f"Loading {INPUT_FILE}...")
    try:
        df = pd.read_parquet(INPUT_FILE)
    except FileNotFoundError:
        print("Input file not found.")
        return

    print(f"Rows: {len(df)}")
    
    # We want to format for instruction tuning.
    # Instruction: Classify...
    # Input: Summary
    # Output: Reasoning + Label
    
    with open(OUTPUT_FILE, 'w') as f:
        count = 0
        for _, row in df.iterrows():
            summary = str(row.get('summary', '')).strip()
            # Handle label list or string
            labels_raw = row.get('labels_list', row.get('labels', ''))
            reasoning = str(row.get('reasoning', '')).strip()
            
            # Format label
            if isinstance(labels_raw, list):
                label_str = ', '.join(labels_raw)
            else:
                label_str = str(labels_raw)
                
            # If no label, skip
            if not label_str or label_str.lower() == 'nan':
                continue
                
            # Construct Prompt
            instruction = "Classify the following Cisco Security Advisory into the correct technical feature label."
            
            # Construct CoT Response
            # If reasoning exists and is decent length, use it. Else just label.
            if reasoning and len(reasoning) > 10 and reasoning.lower() != 'nan':
                 response_text = f"{reasoning}\n\nLabel: {label_str}"
            else:
                 response_text = f"Label: {label_str}"

            # Alpaca/Llama style format often used:
            # text = "### Instruction: ... ### Input: ... ### Response: ..."
            
            text = f"### Instruction:\n{instruction}\n\n### Input:\n{summary}\n\n### Response:\n{response_text}"
            
            record = {"text": text}
            f.write(json.dumps(record) + "\n")
            count += 1
            
    print(f"Successfully wrote {count} records to {OUTPUT_FILE}")

if __name__ == "__main__":
    prepare_data()
