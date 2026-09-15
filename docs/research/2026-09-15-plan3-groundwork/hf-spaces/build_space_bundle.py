"""Prototype: build the Hugging Face Space upload folder from the repo with an ALLOW-LIST (Plan 3 groundwork).

Why a separate folder instead of `hf upload .` from the repo root:
- `upload_folder` / `hf upload` honour the root `.gitignore` SERVER-SIDE (huggingface_hub 1.31.0,
  _upload_pipeline.py: "`.gitignore` rules are enforced server-side"). The repo .gitignore lists corpus/,
  so corpus files would be skipped silently; if a .gitignore already sits on the Space repo it is used too.
- DEFAULT_IGNORE_PATTERNS only covers .git/ and .cache/huggingface/ - NOT .env. An allow-list is the only
  way to be sure the dev key file never leaves the PC.
- The Space needs its own README.md (YAML header), not the GitHub README.

Usage (never reads .env; only allow-listed paths are opened):
    python build_space_bundle.py --repo C:/international_relations            # dry run: list + checks
    python build_space_bundle.py --repo C:/international_relations --out dist/space
Then (implementer, after the user approves the deploy):
    hf upload <user>/<space> dist/space . --repo-type space --commit-message "deploy: <git sha>"
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import shutil
import sys
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "space_template"

ALLOW = [
    "app.py",
    "assistant/*.py",
    "web/*.py", "web/**/*.py", "web/**/*.css", "web/**/*.js",
    "store/*.py", "store/**/*.py",
    "corpus/volumes.json", "corpus/pages.jsonl", "corpus/toc.json", "corpus/missing.json",
    "corpus/index/meta.json", "corpus/index/bm25s/*",
]
FORBIDDEN = [
    ".env", ".env.*", "*.env", "secrets.toml", "*.pem", "*.key", ".gitignore",
    "data/*", "runs/*", "evals/runs/*", "*.pdf", "*/__pycache__/*", "__pycache__/*", "*.pyc", ".git/*",
]
FROM_TEMPLATE = {"README.md": TEMPLATE / "README.md", "requirements.txt": TEMPLATE / "requirements.txt"}
KEY_PATTERNS = [re.compile(rb"sk-(?:proj-|svcacct-)?[A-Za-z0-9_\-]{20,}"), re.compile(rb"hf_[A-Za-z0-9]{30,}")]
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "data", "runs"}
TEXT_SUFFIXES = {".py", ".json", ".jsonl", ".md", ".txt", ".css", ".js", ".toml", ".yaml", ".yml"}


def _match(rel: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(rel, p) for p in patterns)


def collect(repo: Path) -> list[str]:
    files = []
    for path in repo.rglob("*"):
        if any(part in SKIP_DIRS for part in path.relative_to(repo).parts) or not path.is_file():
            continue
        rel = PurePosixPath(path.relative_to(repo).as_posix()).as_posix()
        if _match(rel, ALLOW) and not _match(rel, FORBIDDEN) and not _match(path.name, FORBIDDEN):
            files.append(rel)
    return sorted(files)


def scan_for_keys(repo: Path, files: list[str]) -> list[str]:
    """Paths (and line numbers) that look like an API key. The matched text is never printed."""
    hits = []
    for rel in files:
        if PurePosixPath(rel).suffix not in TEXT_SUFFIXES:
            continue
        for n, line in enumerate((repo / rel).read_bytes().splitlines(), 1):
            if any(p.search(line) for p in KEY_PATTERNS):
                hits.append(f"{rel}:{n}")
    return hits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--out", type=Path, help="copy the bundle here (omit for a dry run)")
    ap.add_argument("--no-key-scan", action="store_true", help="skip the key-pattern scan of bundled text files")
    args = ap.parse_args(argv)
    repo = args.repo.resolve()
    files = collect(repo)
    problems = []
    required = ["corpus/pages.jsonl", "corpus/volumes.json", "corpus/toc.json", "corpus/index/meta.json"]
    problems += [f"missing required file: {r}" for r in required if r not in files]
    if "app.py" not in files:
        problems.append("missing app.py (Plan 3 has not created it yet)")
    key_hits = [] if args.no_key_scan else scan_for_keys(repo, files)
    problems += [f"looks like a key, refusing: {h}" for h in key_hits]
    sizes = {rel: (repo / rel).stat().st_size for rel in files}
    manifest = {
        "repo": str(repo), "file_count": len(files) + len(FROM_TEMPLATE),
        "total_bytes": sum(sizes.values()) + sum(p.stat().st_size for p in FROM_TEMPLATE.values()),
        "largest": sorted(sizes.items(), key=lambda kv: -kv[1])[:5],
        "from_template": sorted(FROM_TEMPLATE), "problems": problems,
        "files": files,
    }
    if args.out:
        if problems:
            print(json.dumps(manifest, ensure_ascii=False, indent=1))
            print("NOT WRITTEN: fix the problems first", file=sys.stderr)
            return 1
        out = args.out.resolve()
        if out.exists():
            shutil.rmtree(out)
        for rel in files:
            (out / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo / rel, out / rel)
        for rel, src in FROM_TEMPLATE.items():
            shutil.copy2(src, out / rel)
        leaked = [p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()
                  and (_match(p.relative_to(out).as_posix(), FORBIDDEN) or _match(p.name, FORBIDDEN))]
        manifest["written_to"], manifest["forbidden_in_output"] = str(out), leaked
    print(json.dumps(manifest, ensure_ascii=False, indent=1))
    return 0 if not manifest.get("forbidden_in_output") else 1


if __name__ == "__main__":
    raise SystemExit(main())
