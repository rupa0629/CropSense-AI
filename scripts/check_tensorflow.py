"""Simple TF import check used during Docker build to fail early if TF is incompatible."""
import sys

try:
    import tensorflow as tf
except Exception as e:
    print("Failed to import TensorFlow:", e, file=sys.stderr)
    sys.exit(2)

print("TensorFlow version:", tf.__version__)
# Check for GPU availability (non-fatal)
try:
    gpus = tf.config.list_physical_devices('GPU')
    print("GPUs detected:", len(gpus))
except Exception:
    print("Could not enumerate GPUs")

sys.exit(0)
