"""Audit a field-image dataset before model training.

Expected layout: DATASET/{train,val,test}/{class_name}/image files.
The audit emits a JSON report and fails on missing classes, unreadable images,
cross-split duplicate files, or insufficient per-class samples.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from models.evaluate_model import CLASS_NAMES

SPLITS = ("train", "val", "test")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def audit_dataset(root: Path, minimum_per_class: int) -> tuple[dict, list[str]]:
    errors: list[str] = []
    counts: dict[str, dict[str, int]] = {}
    corrupt: list[str] = []
    hashes: dict[str, list[str]] = defaultdict(list)
    dimensions: dict[str, dict[str, int]] = defaultdict(lambda: {"min_width": 10**9, "min_height": 10**9})

    for split in SPLITS:
        counts[split] = {}
        for class_name in CLASS_NAMES:
            class_dir = root / split / class_name
            files = (
                [path for path in class_dir.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS]
                if class_dir.exists()
                else []
            )
            counts[split][class_name] = len(files)
            if len(files) < minimum_per_class:
                errors.append(
                    f"{split}/{class_name} has {len(files)} images; minimum is {minimum_per_class}"
                )

            for path in files:
                relative = str(path.relative_to(root))
                try:
                    with Image.open(path) as image:
                        image.verify()
                    with Image.open(path) as image:
                        width, height = image.size
                    dimensions[class_name]["min_width"] = min(dimensions[class_name]["min_width"], width)
                    dimensions[class_name]["min_height"] = min(dimensions[class_name]["min_height"], height)
                    hashes[hashlib.sha256(path.read_bytes()).hexdigest()].append(relative)
                except Exception:
                    corrupt.append(relative)

    duplicates = [paths for paths in hashes.values() if len(paths) > 1]
    cross_split_duplicates = [
        paths for paths in duplicates if len({path.split("/", 1)[0].split("\\", 1)[0] for path in paths}) > 1
    ]
    if corrupt:
        errors.append(f"{len(corrupt)} unreadable image(s)")
    if cross_split_duplicates:
        errors.append(f"{len(cross_split_duplicates)} duplicate image group(s) cross dataset splits")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_root": str(root),
        "classes": CLASS_NAMES,
        "counts": counts,
        "minimum_dimensions": dimensions,
        "corrupt_images": corrupt,
        "cross_split_duplicates": cross_split_duplicates,
        "errors": errors,
        "passed": not errors,
    }
    return report, errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_root", required=True)
    parser.add_argument("--minimum_per_class", type=int, default=30)
    parser.add_argument("--output", default="reports/dataset-audit.json")
    args = parser.parse_args()

    root = Path(args.dataset_root).resolve()
    report, errors = audit_dataset(root, args.minimum_per_class)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(output)
    if errors:
        raise SystemExit("Dataset audit failed:\n- " + "\n- ".join(errors))


if __name__ == "__main__":
    main()
