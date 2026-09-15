import pytest

from prep.volumes import CORPUS_YEARS, VOLUMES


def _pdfs_present() -> bool:
    return all(vol.pdf_path.is_file() for vol in VOLUMES.values())


def pytest_collection_modifyitems(config, items):
    if _pdfs_present():
        return
    skip = pytest.mark.skip(reason="data/ 폴더에 백서 PDF가 없음")
    for item in items:
        if "pdf" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def full_corpus_dir(tmp_path_factory):
    pytest.importorskip("pymupdf", exc_type=ImportError)
    from prep.build import build

    out = tmp_path_factory.mktemp("corpus")
    build(out, list(CORPUS_YEARS))
    return out


@pytest.fixture()
def qa_corpus(tmp_path):
    from assistant.corpus import Corpus
    from tests.corpus_factory import QA_PAGES, QA_TOC, write_corpus

    return Corpus(write_corpus(tmp_path / "corpus", QA_PAGES, QA_TOC))
