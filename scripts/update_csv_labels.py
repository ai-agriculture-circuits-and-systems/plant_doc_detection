#!/usr/bin/env python3
"""
Update CSV files to use label IDs instead of class names.
"""

import json
import csv
from pathlib import Path

def update_csv_labels(csv_dir, labelmap_path):
    """Update all CSV files to use label IDs."""
    # Load labelmap
    with open(labelmap_path, 'r', encoding='utf-8') as f:
        labelmap = json.load(f)
    
    # Create mapping from class name to label ID
    # Need to map from CSV format (e.g., "Bell_pepper leaf") to labelmap format (e.g., "bell_pepper_leaf")
    class_to_id = {}
    
    # First, read original CSV files to get all class name variations
    original_classes = set()
    root_dir = csv_dir.parent.parent
    for csv_file in [root_dir / "train_labels.csv", root_dir / "test_labels.csv"]:
        if csv_file.exists():
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    class_name = row.get('class', '').strip()
                    if class_name and not class_name.isdigit():
                        original_classes.add(class_name)
    
    # Create mapping from original class names to label IDs
    for item in labelmap:
        if item['object_id'] > 0:
            label_id = item['label_id']
            obj_name = item['object_name']  # e.g., "bell_pepper_leaf"
            
            # Generate all possible variations
            variations = [
                obj_name,  # bell_pepper_leaf
                obj_name.replace('_', ' '),  # bell pepper leaf
                obj_name.replace('_', ' ').title(),  # Bell Pepper Leaf
                obj_name.title(),  # Bell_Pepper_Leaf
                obj_name.replace('_', ' ').capitalize(),  # Bell pepper leaf
            ]
            
            # Also try with "leaf" variations
            if obj_name.endswith('_leaf'):
                base = obj_name[:-5]  # Remove "_leaf"
                variations.extend([
                    base.replace('_', ' ') + ' leaf',  # bell pepper leaf
                    base.replace('_', ' ').title() + ' leaf',  # Bell Pepper leaf
                    base.title() + ' leaf',  # Bell_Pepper leaf
                ])
            
            for var in variations:
                class_to_id[var] = label_id
    
    # Map original class names directly
    for orig_class in original_classes:
        # Normalize: lowercase, replace spaces with underscores
        normalized = orig_class.lower().replace(' ', '_')
        # Try to find matching labelmap entry
        for item in labelmap:
            if item['object_id'] > 0 and item['object_name'] == normalized:
                class_to_id[orig_class] = item['label_id']
                break
        # Also try direct match with variations
        if orig_class not in class_to_id:
            # Try case-insensitive match
            for key, val in class_to_id.items():
                if key.lower() == orig_class.lower():
                    class_to_id[orig_class] = val
                    break
    
    # Read CSV files and update
    updated_count = 0
    for csv_file in csv_dir.glob("*.csv"):
        rows = []
        updated = False
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)  # Skip header
            rows.append(header)
            
            for row in reader:
                if len(row) >= 6:
                    class_name = row[5].strip()
                    # Try to find matching label ID
                    label_id = None
                    
                    # Direct match
                    if class_name in class_to_id:
                        label_id = class_to_id[class_name]
                    else:
                        # Try case-insensitive match
                        for key, val in class_to_id.items():
                            if key.lower() == class_name.lower():
                                label_id = val
                                break
                    
                    if label_id is not None:
                        row[5] = str(label_id)
                        updated = True
                    else:
                        print(f"Warning: Could not find label ID for '{class_name}' in {csv_file.name}")
                
                rows.append(row)
        
        if updated:
            # Write back
            with open(csv_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(rows)
            updated_count += 1
    
    print(f"Updated {updated_count} CSV files")

if __name__ == "__main__":
    root_dir = Path(__file__).parent.parent
    csv_dir = root_dir / "plant_diseases" / "csv"
    labelmap_path = root_dir / "plant_diseases" / "labelmap.json"
    
    update_csv_labels(csv_dir, labelmap_path)
