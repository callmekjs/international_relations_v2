import json

import pytest

pytest.importorskip("pymupdf", exc_type=ImportError)

from assistant.search_index import load_index, search  # noqa: E402
from prep.build import build  # noqa: E402

pytestmark = pytest.mark.pdf


def test_build_one_volume(tmp_path):
    stats = build(tmp_path, [2022])
    assert stats["halves"] == 346
    assert stats["citable"] > 300
    for name in ("volumes.json", "toc.json", "missing.json", "pages.jsonl", "index/meta.json"):
        assert (tmp_path / name).is_file(), name
    volumes = json.loads((tmp_path / "volumes.json").read_text(encoding="utf-8"))
    assert volumes["corpus_years"] == [2020, 2021, 2022, 2023, 2024, 2025]
    assert [v["year"] for v in volumes["volumes"]] == [2022]
    assert json.loads((tmp_path / "missing.json").read_text(encoding="utf-8")) == []
    rows = [json.loads(line) for line in (tmp_path / "pages.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 346
    hits = search(load_index(tmp_path / "index"), "정상회담", years=[2022])
    assert hits and all(h["year"] == 2022 for h in hits)
