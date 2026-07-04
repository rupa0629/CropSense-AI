import numpy as np
from PIL import Image

from models.audit_dataset import audit_dataset
from models.evaluate_model import compute_from_cm


def test_model_metrics_include_per_class_f1():
    cm = np.array(
        [
            [8, 2, 0, 0],
            [1, 7, 2, 0],
            [0, 1, 8, 1],
            [0, 0, 1, 9],
        ]
    )
    metrics = compute_from_cm(cm)

    assert 0 < metrics["accuracy"] < 1
    assert 0 < metrics["macro_f1"] < 1
    assert set(metrics["per_class"]["Leaf Blast"]) >= {
        "precision",
        "recall",
        "f1",
        "false_negatives",
    }


def test_dataset_audit_passes_clean_independent_splits(tmp_path):
    colors = {"train": 20, "val": 80, "test": 140}
    classes = ["Leaf Blast", "Brown Spot", "Bacterial Blight", "Healthy"]
    for split, base in colors.items():
        for class_index, class_name in enumerate(classes):
            directory = tmp_path / split / class_name
            directory.mkdir(parents=True)
            Image.new(
                "RGB",
                (64, 64),
                color=(base, class_index * 30, 10),
            ).save(directory / f"{split}-{class_index}.png")

    report, errors = audit_dataset(tmp_path, minimum_per_class=1)

    assert errors == []
    assert report["passed"] is True


def test_dataset_audit_rejects_cross_split_duplicates(tmp_path):
    classes = ["Leaf Blast", "Brown Spot", "Bacterial Blight", "Healthy"]
    duplicate = Image.new("RGB", (32, 32), color=(10, 20, 30))
    for split_index, split in enumerate(("train", "val", "test")):
        for index, class_name in enumerate(classes):
            directory = tmp_path / split / class_name
            directory.mkdir(parents=True)
            image = duplicate if class_name == "Leaf Blast" else Image.new(
                "RGB", (32, 32), color=(index * 40, split_index * 50, 90)
            )
            image.save(directory / f"{split}-{index}.png")

    report, errors = audit_dataset(tmp_path, minimum_per_class=1)

    assert report["passed"] is False
    assert any("cross dataset splits" in error for error in errors)
