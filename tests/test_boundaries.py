import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SDK_IMPORT = re.compile(r"^\s*(import|from)\s+(openai|httpx2?)\b", re.MULTILINE)


def test_only_the_adapter_imports_the_openai_sdk():
    offenders = [path.name for path in sorted((ROOT / "assistant").glob("*.py"))
                 if path.name != "llm_openai.py" and SDK_IMPORT.search(path.read_text(encoding="utf-8"))]
    assert offenders == []


def test_importing_the_assistant_loads_neither_the_sdk_nor_pymupdf():
    code = ("import sys, assistant, assistant.runner, assistant.loop, assistant.tools; "
            "print(sorted(m for m in ('openai', 'httpx2', 'pymupdf', 'fitz') if m in sys.modules))")
    done = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True)
    assert done.stdout.strip() == "[]"
