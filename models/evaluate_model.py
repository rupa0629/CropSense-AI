"""Evaluate trained rice model: confusion matrix, accuracy, precision, recall.

Expected test set:
  dataset_root/test/<class_name>/*.jpg

Example:
  python models/evaluate_model.py --dataset_root "C:/data/rice_dataset" --model_path "models/rice_disease_model.h5"
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import tensorflow as tf

CLASS_NAMES = ["Leaf Blast", "Brown Spot", "Bacterial Blight", "Healthy"]
IMG_SIZE = (224, 224)
BATCH_SIZE = 32


def safe_div(a: float, b: float) -> float:
    return float(a / b) if b else 0.0


def compute_from_cm(cm: np.ndarray) -> dict:
    total = int(cm.sum())
    correct = int(np.trace(cm))
    accuracy = safe_div(correct, total)

    precisions = []
    recalls = []
    per_class = {}

    for i, cls in enumerate(CLASS_NAMES):
        tp = int(cm[i, i])
        fp = int(cm[:, i].sum() - tp)
        fn = int(cm[i, :].sum() - tp)
        p = safe_div(tp, tp + fp)
        r = safe_div(tp, tp + fn)
        precisions.append(p)
        recalls.append(r)
        per_class[cls] = {"precision": p, "recall": r, "support": int(cm[i, :].sum())}

    return {
        "accuracy": accuracy,
        "macro_precision": float(np.mean(precisions)) if precisions else 0.0,
        "macro_recall": float(np.mean(recalls)) if recalls else 0.0,
        "per_class": per_class,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_root", required=True)
    parser.add_argument("--model_path", default="models/rice_disease_model.keras")
    args = parser.parse_args()

    test_dir = Path(args.dataset_root).resolve() / "test"
    if not test_dir.exists():
        raise SystemExit(f"Missing test folder: {test_dir}")

    model_path = Path(args.model_path).resolve()
    if not model_path.exists():
        raise SystemExit(f"Model file not found: {model_path}")

    test_ds = tf.keras.utils.image_dataset_from_directory(
        test_dir,
        labels="inferred",
        label_mode="categorical",
        class_names=CLASS_NAMES,
        image_size=IMG_SIZE,
        batch_size=BATCH_SIZE,
        shuffle=False,
    )

    y_true = []
    y_pred = []

    model = tf.keras.models.load_model(model_path)

    for x_batch, y_batch in test_ds:
        probs = model.predict(x_batch, verbose=0)
        y_pred.extend(np.argmax(probs, axis=1).tolist())
        y_true.extend(np.argmax(y_batch.numpy(), axis=1).tolist())

    y_true_arr = np.array(y_true, dtype=np.int32)
    y_pred_arr = np.array(y_pred, dtype=np.int32)

    cm = tf.math.confusion_matrix(y_true_arr, y_pred_arr, num_classes=len(CLASS_NAMES)).numpy()
    metrics = compute_from_cm(cm)

    print("\n=== Evaluation ===")
    print(f"Accuracy: {metrics['accuracy']:.4f}")
    print(f"Macro Precision: {metrics['macro_precision']:.4f}")
    print(f"Macro Recall: {metrics['macro_recall']:.4f}")

    print("\nConfusion Matrix (rows=true, cols=pred):")
    print("\t" + "\t".join(CLASS_NAMES))
    for i, cls in enumerate(CLASS_NAMES):
        row = "\t".join(str(int(v)) for v in cm[i])
        print(f"{cls}\t{row}")


if __name__ == "__main__":
    main()
