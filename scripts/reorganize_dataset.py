#!/usr/bin/env python3
"""
Reorganize PlantDoc dataset to standard structure.
Converts from TRAIN/TEST structure with CSV files to standard category-based structure.
"""

import os
import csv
import shutil
import json
from pathlib import Path
from collections import defaultdict

def get_all_classes(csv_files):
    """Extract all unique classes from CSV files."""
    classes = set()
    for csv_file in csv_files:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                class_name = row.get('class', '').strip()
                if class_name and not class_name.isdigit():
                    classes.add(class_name)
    return sorted(classes)

def convert_bbox_format(xmin, ymin, xmax, ymax):
    """Convert from (xmin, ymin, xmax, ymax) to (x, y, width, height)."""
    x = float(xmin)
    y = float(ymin)
    width = float(xmax) - float(xmin)
    height = float(ymax) - float(ymin)
    return x, y, width, height

def create_per_image_csvs(root_dir, csv_file, images_dir, output_csv_dir):
    """Create per-image CSV annotation files."""
    os.makedirs(output_csv_dir, exist_ok=True)
    
    annotations_by_image = defaultdict(list)
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            filename = row['filename'].strip()
            class_name = row['class'].strip()
            
            # Skip invalid entries
            if not filename or not class_name or class_name.isdigit():
                continue
            
            # Convert bbox format
            x, y, width, height = convert_bbox_format(
                row['xmin'], row['ymin'], row['xmax'], row['ymax']
            )
            
            annotations_by_image[filename].append({
                'x': x,
                'y': y,
                'width': width,
                'height': height,
                'label': class_name
            })
    
    # Write per-image CSV files
    for filename, annotations in annotations_by_image.items():
        # Get image stem (filename without extension)
        stem = Path(filename).stem
        
        # Check if image exists
        image_path = None
        for ext in ['.jpg', '.jpeg', '.png']:
            potential_path = images_dir / f"{stem}{ext}"
            if potential_path.exists():
                image_path = potential_path
                break
        
        if not image_path:
            # Try with original filename
            potential_path = images_dir / filename
            if potential_path.exists():
                image_path = potential_path
            else:
                print(f"Warning: Image not found for {filename}")
                continue
        
        # Write CSV file
        csv_path = output_csv_dir / f"{stem}.csv"
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['#item', 'x', 'y', 'width', 'height', 'label'])
            
            for idx, ann in enumerate(annotations):
                # Get label ID from class name (will be set later)
                writer.writerow([
                    idx,
                    ann['x'],
                    ann['y'],
                    ann['width'],
                    ann['height'],
                    ann['label']
                ])
    
    return len(annotations_by_image)

def create_labelmap(classes, output_path):
    """Create labelmap.json file."""
    labelmap = [
        {
            "object_id": 0,
            "label_id": 0,
            "keyboard_shortcut": "0",
            "object_name": "background"
        }
    ]
    
    # Create mapping from class name to ID
    class_to_id = {}
    for idx, class_name in enumerate(sorted(classes), start=1):
        class_to_id[class_name] = idx
        labelmap.append({
            "object_id": idx,
            "label_id": idx,
            "keyboard_shortcut": str(idx),
            "object_name": class_name.lower().replace(' ', '_')
        })
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(labelmap, f, indent=2, ensure_ascii=False)
    
    return class_to_id

def copy_images(source_dir, dest_dir):
    """Copy images to destination directory."""
    os.makedirs(dest_dir, exist_ok=True)
    
    image_extensions = ['.jpg', '.jpeg', '.png']
    copied = 0
    
    for ext in image_extensions:
        for img_path in source_dir.glob(f"*{ext}"):
            dest_path = dest_dir / img_path.name
            if not dest_path.exists():
                shutil.copy2(img_path, dest_path)
                copied += 1
    
    return copied

def create_sets_files(root_dir, train_csv, test_csv, images_dir, sets_dir):
    """Create dataset split files."""
    os.makedirs(sets_dir, exist_ok=True)
    
    def get_image_stems(csv_file):
        stems = set()
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                filename = row['filename'].strip()
                if filename:
                    stem = Path(filename).stem
                    # Verify image exists
                    for ext in ['.jpg', '.jpeg', '.png']:
                        if (images_dir / f"{stem}{ext}").exists():
                            stems.add(stem)
                            break
        return stems
    
    train_stems = get_image_stems(train_csv)
    test_stems = get_image_stems(test_csv)
    
    # Write split files
    with open(sets_dir / 'train.txt', 'w', encoding='utf-8') as f:
        for stem in sorted(train_stems):
            f.write(f"{stem}\n")
    
    with open(sets_dir / 'test.txt', 'w', encoding='utf-8') as f:
        for stem in sorted(test_stems):
            f.write(f"{stem}\n")
    
    # Create all.txt
    all_stems = train_stems | test_stems
    with open(sets_dir / 'all.txt', 'w', encoding='utf-8') as f:
        for stem in sorted(all_stems):
            f.write(f"{stem}\n")
    
    # For validation, we'll use a subset of training (80/20 split)
    train_list = sorted(train_stems)
    val_size = len(train_list) // 5  # 20% for validation
    val_stems = set(train_list[:val_size])
    train_only_stems = set(train_list[val_size:])
    
    with open(sets_dir / 'val.txt', 'w', encoding='utf-8') as f:
        for stem in sorted(val_stems):
            f.write(f"{stem}\n")
    
    # Update train.txt to exclude validation set
    with open(sets_dir / 'train.txt', 'w', encoding='utf-8') as f:
        for stem in sorted(train_only_stems):
            f.write(f"{stem}\n")
    
    # Create train_val.txt
    train_val_stems = train_only_stems | val_stems
    with open(sets_dir / 'train_val.txt', 'w', encoding='utf-8') as f:
        for stem in sorted(train_val_stems):
            f.write(f"{stem}\n")
    
    return len(train_only_stems), len(val_stems), len(test_stems)

def main():
    root_dir = Path(__file__).parent.parent
    category_name = "plant_diseases"
    
    # Create directory structure
    category_dir = root_dir / category_name
    csv_dir = category_dir / "csv"
    images_dir = category_dir / "images"
    sets_dir = category_dir / "sets"
    
    print("Creating directory structure...")
    os.makedirs(csv_dir, exist_ok=True)
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(sets_dir, exist_ok=True)
    
    # Get all classes
    print("Extracting classes...")
    train_csv = root_dir / "train_labels.csv"
    test_csv = root_dir / "test_labels.csv"
    classes = get_all_classes([train_csv, test_csv])
    print(f"Found {len(classes)} classes")
    
    # Create labelmap
    print("Creating labelmap.json...")
    labelmap_path = category_dir / "labelmap.json"
    class_to_id = create_labelmap(classes, labelmap_path)
    
    # Copy images from TRAIN and TEST
    print("Copying images...")
    train_images_dir = root_dir / "TRAIN"
    test_images_dir = root_dir / "TEST"
    
    train_count = copy_images(train_images_dir, images_dir)
    test_count = copy_images(test_images_dir, images_dir)
    print(f"Copied {train_count} train images and {test_count} test images")
    
    # Create per-image CSV files
    print("Creating per-image CSV annotations...")
    train_csv_count = create_per_image_csvs(
        root_dir, train_csv, images_dir, csv_dir
    )
    test_csv_count = create_per_image_csvs(
        root_dir, test_csv, images_dir, csv_dir
    )
    print(f"Created {train_csv_count} train CSV files and {test_csv_count} test CSV files")
    
    # Create sets files
    print("Creating dataset split files...")
    train_size, val_size, test_size = create_sets_files(
        root_dir, train_csv, test_csv, images_dir, sets_dir
    )
    print(f"Train: {train_size}, Val: {val_size}, Test: {test_size}")
    
    print("\nDataset reorganization complete!")
    print(f"Standard structure created in: {category_dir}")

if __name__ == "__main__":
    main()
