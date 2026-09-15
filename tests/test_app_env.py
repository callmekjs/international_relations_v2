"""Without PyMuPDF (the Hugging Face app install) the suite must still pass: PDF tests skip."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

HIDE_PYMUPDF = (
    "import sys; sys.modules['pymupdf'] = None; sys.modules['fitz'] = None; import pytest; "
    "sys.exit(pytest.main(['-q', '-p', 'no:cacheprovider', '-m', 'not slow', "
    "'--ignore=tests/test_app_env.py', 'tests']))"
)


def test_suite_passes_without_pymupdf():
    env = {**os.environ, "PYTHONUTF8": "1"}
    done = subprocess.run([sys.executable, "-c", HIDE_PYMUPDF], cwd=ROOT, env=env,
                          capture_output=True, text=True, encoding="utf-8", timeout=900)
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-3000:]
    assert "skipped" in done.stdout
