#!/usr/bin/env python3
"""
Merge definitions (descriptions) from a Frontiers Update YAML into the main taxonomy file.
Preserves existing fields (presence, docs) and structure.
"""

import yaml
import sys
import os

# Preserve YAML formatting as much as possible
# But Ruamel or PyYAML default dumpers might change style. 
# For now, we load both as python objects, merge, and dump.
# Ideally we would use ruamel.yaml to preserve comments, but let's stick to standard PyYAML if available or simple logic.

def load_yaml(path):
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def save_yaml(path, data):
    with open(path, 'w') as f:
        # Sort keys false to keep order? No, PyYAML doesn't guarantee order of list items unless we are careful.
        # But 'data' is a list.
        yaml.dump(data, f, sort_keys=False, width=120)

def main():
    if len(sys.argv) != 3:
        print("Usage: python merge_taxonomy_updates.py <main_taxonomy.yml> <update_batch.yml>")
        sys.exit(1)

    main_path = sys.argv[1]
    update_path = sys.argv[2]

    print(f"Loading main taxonomy: {main_path}")
    main_data = load_yaml(main_path)
    # Convert list to dict for easy lookup by label
    main_dict = {item['label']: item for item in main_data}

    print(f"Loading updates: {update_path}")
    update_data = load_yaml(update_path)

    updates_count = 0
    added_count = 0
    for update_item in update_data:
        label = update_item['label']
        if label in main_dict:
            # Merge description
            if 'description' in update_item:
                main_dict[label]['description'] = update_item['description']
                updates_count += 1
                print(f"Updated description for {label}")
        else:
            print(f"Adding new label {label} to taxonomy")
            main_data.append(update_item)
            main_dict[label] = update_item # Keep dict in sync roughly, though main_data is what we save
            added_count += 1

    # Reconstruct list logic is tricky if we appended to main_data.
    # Actually, main_data is a list of dict objects. 
    # If we appended to main_data, those objects are already at the end of the list.
    # The previous logic "new_data = [] ... for item in main_data" was to preserve order BUT
    # it was iterating main_data (original list) and looking up in main_dict (modified objects).
    # Since main_data contains REFERENCES to the objects in main_dict (because we built main_dict from main_data items),
    # modifying main_dict[label] MODIFIES the item in main_data directly in memory.
    # So we don't need to reconstruct the list at all if we just modified the objects in place!
    # And if we appended to main_data, they are there too.
    
    # So we can just save `main_data`.
    
    print(f"Saving merged taxonomy to {main_path}...")
    save_yaml(main_path, main_data)
    print(f"Done. Updated {updates_count} definitions, Added {added_count} new labels.")

if __name__ == "__main__":
    main()
