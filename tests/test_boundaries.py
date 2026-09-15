import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SDK_IMPORT = re.compile(r"^\s*(import|from)\s+(openai|httpx2?)\b", re.MULTILINE)


def test_only_the_adapter_imports_the_openai_sdk():
    offenders = [path.name for path in sorted((ROOT / "assistant").glob("*.py"))
                 if path.name != "llm_openai.py" and SDK_IMPORT.search(path.read_text(encoding="utf-8"))]
    assert offenders == []
