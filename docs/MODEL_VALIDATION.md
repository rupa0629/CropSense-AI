# Model validation and agronomist approval

CropSense predictions are screening results until the model has passed an
independent field test and an agronomist has signed the release record.

## Required dataset

Use farmer-consented, agronomist-labelled photographs covering:

- all supported disease classes plus healthy and non-rice rejection images;
- multiple rice varieties and seed sources;
- seedling, tillering, panicle initiation, heading and grain-filling stages;
- close-up leaves, whole plants and field-pattern images;
- multiple phones, orientations, backgrounds, lighting and weather conditions;
- farms that were not represented in training.

Keep `train`, `val`, and `test` farm-independent. Images from the same plant,
field burst, or farmer must never occur across different splits.

## Validation commands

```powershell
python -m models.audit_dataset --dataset_root C:\data\rice-field-dataset
python -m models.evaluate_model `
  --dataset_root C:\data\rice-field-dataset `
  --model_path models\rice_disease_model.keras `
  --output_dir reports/model-evaluation `
  --minimum_macro_f1 0.80
```

The evaluator writes:

- `model-evaluation.json`
- `per-class-metrics.csv`
- `confusion-matrix.csv`

Do not promote a model based on overall accuracy alone. Review per-class
precision, recall, F1, false-negative patterns, calibration, and performance
by farm, variety, crop stage, device and lighting condition.

## Agronomist release gate

Create a release record containing:

- model checksum and training code commit;
- dataset version, consent status and split methodology;
- complete evaluation artifacts;
- at least two independent agronomist reviewers;
- known limitations and unsupported symptoms;
- approval date, expiry/re-review date and rollback model;
- signed decision: approved, approved with restrictions, or rejected.

Never label a model as field validated until this record exists.
