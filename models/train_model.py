"""Train a higher-accuracy rice disease classifier and save .h5 model.

Expected dataset structure:
  dataset_root/
    train/
      Leaf Blast/
      Brown Spot/
      Bacterial Blight/
      Healthy/
    val/
      Leaf Blast/
      Brown Spot/
      Bacterial Blight/
      Healthy/

Example:
  python models/train_model.py --dataset_root "C:/data/rice_dataset" --epochs 24 --fine_tune_epochs 12
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import tensorflow as tf

CLASS_NAMES = ["Leaf Blast", "Brown Spot", "Bacterial Blight", "Healthy"]
IMG_SIZE = (224, 224)
BATCH_SIZE = 32
SEED = 42


def _class_dir_names(split_dir: Path) -> set[str]:
    if not split_dir.exists():
        return set()
    return {p.name for p in split_dir.iterdir() if p.is_dir()}


def _class_counts(dataset_root: Path, split: str) -> dict[str, int]:
    split_dir = dataset_root / split
    counts: dict[str, int] = {c: 0 for c in CLASS_NAMES}
    for cls in CLASS_NAMES:
        cls_dir = split_dir / cls
        if not cls_dir.exists():
            continue
        # Count common image extensions only.
        exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
        counts[cls] = sum(1 for p in cls_dir.rglob("*") if p.is_file() and p.suffix.lower() in exts)
    return counts


def _build_class_weights(counts: dict[str, int]) -> np.ndarray:
    # Inverse-frequency weights; normalize by mean to keep scale stable.
    values = np.array([max(1, counts[c]) for c in CLASS_NAMES], dtype=np.float32)
    inv = values.max() / values
    return inv / (inv.mean() + 1e-8)


def load_split(dataset_root: Path, split: str):
    split_dir = dataset_root / split
    if not split_dir.exists():
        raise FileNotFoundError(f"Missing split folder: {split_dir}")

    # Cleaner labels: ensure the dataset uses your expected class folder names.
    present_dirs = _class_dir_names(split_dir)
    missing = set(CLASS_NAMES) - present_dirs
    if missing:
        raise FileNotFoundError(
            f"Missing expected class folders in {split_dir}: {sorted(missing)}. "
            "Labels must be stored under the correct class directories."
        )
    unexpected = present_dirs - set(CLASS_NAMES)
    if unexpected:
        print(f"[WARN] Unexpected folders in {split_dir} (ignored by class_names): {sorted(unexpected)}")

    counts = _class_counts(dataset_root, split)
    print(f"{split.capitalize()} class counts: {counts}")
    if any(v < 5 for v in counts.values()):
        print("[WARN] Some classes have very few images; accuracy may be limited.")

    ds = tf.keras.utils.image_dataset_from_directory(
        split_dir,
        labels="inferred",
        label_mode="categorical",
        class_names=CLASS_NAMES,
        image_size=IMG_SIZE,
        batch_size=BATCH_SIZE,
        shuffle=(split == "train"),
        seed=SEED,
    )

    ds = ds.cache().prefetch(tf.data.AUTOTUNE)
    return ds


def build_model() -> tf.keras.Model:
    base = tf.keras.applications.EfficientNetB0(
        include_top=False,
        weights="imagenet",
        input_shape=(IMG_SIZE[0], IMG_SIZE[1], 3),
    )
    base.trainable = False

    augmentation = tf.keras.Sequential(
        [
            tf.keras.layers.RandomFlip("horizontal"),
            tf.keras.layers.RandomRotation(0.12),
            tf.keras.layers.RandomZoom(0.2),
            tf.keras.layers.RandomTranslation(height_factor=0.1, width_factor=0.1),
            tf.keras.layers.RandomContrast(0.2),
            tf.keras.layers.RandomBrightness(0.2),
            tf.keras.layers.RandomSaturation(0.2),
            tf.keras.layers.RandomHue(0.02),
        ],
        name="augmentation",
    )

    inputs = tf.keras.Input(shape=(IMG_SIZE[0], IMG_SIZE[1], 3))
    x = augmentation(inputs)
    x = tf.keras.applications.efficientnet.preprocess_input(x)
    x = base(x, training=False)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Dropout(0.35)(x)
    outputs = tf.keras.layers.Dense(len(CLASS_NAMES), activation="softmax")(x)
    model = tf.keras.Model(inputs, outputs)

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=3e-4),
        loss=tf.keras.losses.CategoricalCrossentropy(label_smoothing=0.03),
        metrics=["accuracy"],
    )
    return model


def find_backbone(model: tf.keras.Model):
    for layer in model.layers:
        if isinstance(layer, tf.keras.Model) and "efficientnet" in layer.name.lower():
            return layer
    return None


def fine_tune(
    model: tf.keras.Model,
    unfreeze_last: int = 80,
) -> None:
    base = find_backbone(model)
    if base is None:
        return

    base.trainable = True
    # Unfreeze the last N layers, but keep BatchNorm frozen to reduce instability.
    freeze_upto = max(0, len(base.layers) - unfreeze_last)
    for i, layer in enumerate(base.layers):
        layer.trainable = i >= freeze_upto
        if isinstance(layer, tf.keras.layers.BatchNormalization):
            layer.trainable = False

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-5),
        loss=tf.keras.losses.CategoricalCrossentropy(label_smoothing=0.01),
        metrics=["accuracy"],
    )


def add_class_balance_sample_weights(
    train_ds: tf.data.Dataset, dataset_root: Path
) -> tuple[tf.data.Dataset, np.ndarray]:
    counts = _class_counts(dataset_root, "train")
    class_weights = _build_class_weights(counts)
    # Targeted boost for Leaf Blast recall (common confusion with Bacterial Blight).
    leaf_blast_idx = CLASS_NAMES.index("Leaf Blast")
    class_weights[leaf_blast_idx] *= 1.35
    class_weights = class_weights / (class_weights.mean() + 1e-8)

    # Convert one-hot labels into per-example weights.
    # Keras will consume this as (x, y, sample_weight).
    class_weights_tf = tf.constant(class_weights, dtype=tf.float32)

    def _map(x, y):
        class_idx = tf.argmax(y, axis=-1, output_type=tf.int32)
        w = tf.gather(class_weights_tf, class_idx)
        return x, y, w

    return train_ds.map(_map, num_parallel_calls=tf.data.AUTOTUNE), class_weights


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_root", required=True)
    parser.add_argument("--epochs", type=int, default=24)
    parser.add_argument("--fine_tune_epochs", type=int, default=12)
    parser.add_argument("--out", default="models/rice_disease_model.keras")
    parser.add_argument("--unfreeze_last", type=int, default=120)
    parser.set_defaults(balance_classes=True)
    parser.add_argument(
        "--no_balance_classes",
        dest="balance_classes",
        action="store_false",
        help="Disable class balancing sample weights.",
    )
    args = parser.parse_args()

    tf.keras.utils.set_random_seed(SEED)

    dataset_root = Path(args.dataset_root).resolve()
    train_ds = load_split(dataset_root, "train")
    val_ds = load_split(dataset_root, "val")

    if args.balance_classes:
        train_ds, class_weights = add_class_balance_sample_weights(train_ds, dataset_root)
        print(f"Using class balance weights: {dict(zip(CLASS_NAMES, class_weights.tolist()))}")

    model = build_model()

    best_path = str((Path(args.out).resolve()).with_suffix(".best.weights.h5"))

    callbacks_stage1 = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_accuracy",
            patience=5,
            restore_best_weights=True,
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=2,
            min_lr=1e-7,
        ),
        tf.keras.callbacks.ModelCheckpoint(
            filepath=best_path,
            monitor="val_accuracy",
            mode="max",
            save_best_only=True,
            save_weights_only=True,
        ),
    ]

    model.fit(train_ds, validation_data=val_ds, epochs=args.epochs, callbacks=callbacks_stage1)

    fine_tune(model, unfreeze_last=args.unfreeze_last)

    # Fresh callbacks so "best checkpoint" tracking works per stage.
    callbacks_stage2 = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_accuracy",
            patience=5,
            restore_best_weights=True,
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=2,
            min_lr=1e-7,
        ),
        tf.keras.callbacks.ModelCheckpoint(
            filepath=best_path,
            monitor="val_accuracy",
            mode="max",
            save_best_only=True,
            save_weights_only=True,
        ),
    ]

    model.fit(train_ds, validation_data=val_ds, epochs=args.fine_tune_epochs, callbacks=callbacks_stage2)

    # Ensure the final saved model is the best (by val_accuracy) across both stages.
    best_model_path = Path(best_path)
    if best_model_path.exists():
        model.load_weights(str(best_model_path))

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(out_path, include_optimizer=False)
    print(f"Saved trained model: {out_path}")


if __name__ == "__main__":
    main()
