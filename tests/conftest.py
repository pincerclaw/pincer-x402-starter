import os
import pytest
from solders.keypair import Keypair

# Generate valid dummy keys
dummy_svm_key = str(Keypair())

# Set dummy environment variables for testing
# This must run before src.config is imported by any test
os.environ.setdefault("SVM_ADDRESS", "11111111111111111111111111111111")
os.environ.setdefault("TREASURY_SVM_ADDRESS", "11111111111111111111111111111111")
os.environ.setdefault("TREASURY_SVM_PRIVATE_KEY", dummy_svm_key)
os.environ.setdefault("TREASURY_EVM_PRIVATE_KEY", "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef")
os.environ.setdefault("EVM_PRIVATE_KEY", "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef")
