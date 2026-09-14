import pytest

from prep.volumes import VOLUMES


def _pdfs_present() -> bool:
    return all(vol.pdf_path.is_file() for vol in VOLUMES.values())


def pytest_collection_modifyitems(config, items):
    if _pdfs_present():
        return
    skip = pytest.mark.skip(reason="data/ 폴더에 백서 PDF가 없음")
    for item in items:
        if "pdf" in item.keywords:
            item.add_marker(skip)
