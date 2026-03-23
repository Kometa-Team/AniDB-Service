"""Configure test environment before app module is imported."""

import os

os.environ.setdefault("CLIENT_ID", "test-client-id")
os.environ.setdefault("CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("REDIRECT_URI", "http://localhost:8080/callback")
