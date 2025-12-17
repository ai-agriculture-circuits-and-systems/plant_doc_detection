#!/usr/bin/env python3
"""
Convert PlantDoc dataset annotations to COCO JSON format.

This script converts per-image CSV annotations in the PlantDoc dataset
into COCO-style JSON files.

Usage:
    python scripts/convert_to_coco.py --root . --out annotations --splits train val test
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from PIL import Image


def read_split_list(split_file: Path) -> List[str]:
    """Read image base names (without extension) from a split file."""
    if not split_file.exists():
        return []
    lines = [line.strip() for line in split_file.read_text(encoding="utf-8").splitlines()]
    return [line for line in lines if line]


def image_size(image_path: Path) -> Tuple[int, int]:
    """Return (width, height) for an image path using PIL."""
    with Image.open(image_path) as img:
        return img.width, img.height


def load_labelmap(labelmap_path: Path) -> Dict[str, int]:
    """Load labelmap and create mapping from class name to category ID."""
    with open(labelmap_path, 'r', encoding='utf-8') as f:
        labelmap = json.load(f)
    
    # Create mapping from class name (normalized) to category ID
    class_to_id = {}
    for item in labelmap:
        if item['object_id'] > 0:  # Skip background
            obj_name = item['object_name']
            label_id = item['label_id']
            # Map various formats
            class_to_id[obj_name] = label_id
            class_to_id[obj_name.replace('_', ' ')] = label_id
            class_to_id[obj_name.replace('_', ' ').title()] = label_id
            class_to_id[obj_name.title()] = label_id
    
    return class_to_id


def parse_csv_boxes(csv_path: Path, class_to_id: Dict[str, int]) -> List[Dict]:
    """Parse a single per-image CSV file and return COCO-style annotations."""
    if not csv_path.exists():
        return []
    
    annotations = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return annotations
        
        for row in reader:
            try:
                # Get coordinates
                x = float(row.get('x', 0))
                y = float(row.get('y', 0))
                width = float(row.get('width', 0))
                height = float(row.get('height', 0))
                
                # Get label (can be ID or class name)
                label = row.get('label', '').strip()
                
                # Determine category_id
                category_id = None
                if label.isdigit():
                    category_id = int(label)
                else:
                    # Try to find matching category ID
                    normalized = label.lower().replace(' ', '_')
                    if normalized in class_to_id:
                        category_id = class_to_id[normalized]
                    else:
                        # Try case-insensitive match
                        for key, val in class_to_id.items():
                            if key.lower() == label.lower():
                                category_id = val
                                break
                
                if category_id is None:
                    continue
                
                # Create annotation
                annotations.append({
                    'x': x,
                    'y': y,
                    'width': width,
                    'height': height,
                    'category_id': category_id,
                    'area': width * height,
                })
            except (ValueError, KeyError):
                continue
    
    return annotations


def collect_annotations_for_split(
    category_root: Path,
    split: str,
    category_name: str,
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Collect COCO dictionaries for images, annotations, and categories."""
    images_dir = category_root / "images"
    annotations_dir = category_root / "csv"
    sets_dir = category_root / "sets"
    labelmap_path = category_root / "labelmap.json"
    
    # Load labelmap
    class_to_id = load_labelmap(labelmap_path)
    
    # Load labelmap to get categories
    with open(labelmap_path, 'r', encoding='utf-8') as f:
        labelmap = json.load(f)
    
    # Create categories list
    categories = []
    for item in labelmap:
        if item['object_id'] > 0:  # Skip background
            categories.append({
                "id": item['label_id'],
                "name": item['object_name'],
                "supercategory": "plant_disease"
            })
    
    # Read split list
    split_file = sets_dir / f"{split}.txt"
    image_stems = set(read_split_list(split_file))
    
    if not image_stems:
        # Fall back to all images
        image_stems = {p.stem for p in images_dir.glob("*.jpg")}
        image_stems.update({p.stem for p in images_dir.glob("*.jpeg")})
        image_stems.update({p.stem for p in images_dir.glob("*.png")})
    
    images = []
    annotations = []
    
    image_id_counter = 1
    ann_id_counter = 1
    
    for stem in sorted(image_stems):
        # Find image file
        img_path = None
        for ext in ['.jpg', '.jpeg', '.png']:
            potential_path = images_dir / f"{stem}{ext}"
            if potential_path.exists():
                img_path = potential_path
                break
        
        if not img_path:
            continue
        
        # Get image size
        width, height = image_size(img_path)
        
        # Add image entry
        images.append({
            "id": image_id_counter,
            "file_name": str(img_path.relative_to(category_root.parent)),
            "width": width,
            "height": height,
        })
        
        # Parse annotations
        csv_path = annotations_dir / f"{stem}.csv"
        boxes = parse_csv_boxes(csv_path, class_to_id)
        
        for box in boxes:
            annotations.append({
                "id": ann_id_counter,
                "image_id": image_id_counter,
                "category_id": box['category_id'],
                "bbox": [box['x'], box['y'], box['width'], box['height']],
                "area": box['area'],
                "iscrowd": 0,
            })
            ann_id_counter += 1
        
        image_id_counter += 1
    
    return images, annotations, categories


def build_coco_dict(
    images: List[Dict],
    annotations: List[Dict],
    categories: List[Dict],
    description: str,
) -> Dict:
    """Build a complete COCO dict from components."""
    return {
        "info": {
            "year": 2020,
            "version": "1.0.0",
            "description": description,
            "url": "https://github.com/pratikkayal/PlantDoc-Dataset",
        },
        "images": images,
        "annotations": annotations,
        "categories": categories,
        "licenses": [],
    }


def convert(
    root: Path,
    out_dir: Path,
    category: str,
    splits: Sequence[str],
) -> None:
    """Convert dataset to COCO JSON files."""
    out_dir.mkdir(parents=True, exist_ok=True)
    
    category_root = root / category
    
    for split in splits:
        images, annotations, categories = collect_annotations_for_split(
            category_root, split, category
        )
        
        desc = f"PlantDoc {category} {split} split"
        coco = build_coco_dict(images, annotations, categories, desc)
        
        out_path = out_dir / f"{category}_instances_{split}.json"
        out_path.write_text(json.dumps(coco, indent=2), encoding="utf-8")
        
        print(f"Generated {out_path}: {len(images)} images, {len(annotations)} annotations, {len(categories)} categories")


def main() -> int:
    """Entry point for the converter CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Dataset root directory (default: dataset root)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "annotations",
        help="Output directory for COCO JSON files (default: <root>/annotations)",
    )
    parser.add_argument(
        "--category",
        type=str,
        default="plant_diseases",
        help="Category name (default: plant_diseases)",
    )
    parser.add_argument(
        "--splits",
        nargs="+",
        type=str,
        default=["train", "val", "test"],
        choices=["train", "val", "test"],
        help="Dataset splits to generate (default: train val test)",
    )
    
    args = parser.parse_args()
    
    convert(
        root=Path(args.root),
        out_dir=Path(args.out),
        category=args.category,
        splits=args.splits,
    )
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
