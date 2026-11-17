from __future__ import annotations

import json
from pathlib import Path

import pytest

from hantts.core.catalog import CatalogWarning, load_catalog
from hantts.core.errors import CatalogError


def test_real_catalog_is_pinned() -> None:
    catalog = load_catalog(Path("engines/catalog/catalog.json"))
    assert {e.id for e in catalog.engines} == {"supertonic", "melo", "windows"}
    supertonic = catalog.require("supertonic")
    assert supertonic.assets[0].verified
    assert all(a.verified for a in supertonic.assets)
    assert not any("resolve/main/" in u for a in supertonic.assets for u in a.urls)
    assert catalog.warnings == () or all(isinstance(w, CatalogWarning) for w in catalog.warnings)
    assert catalog.warnings == ()
    checked = {lic.name: lic.default_checked for lic in catalog.require("melo").licenses}
    assert checked["MIT (MeloTTS, gnyong 변환본)"] is True
    assert checked["kykim/bert-kor-base (BERT 사용 시, 라이선스 확인 필요)"] is True
    super_checked = {lic.name: lic.default_checked for lic in supertonic.licenses}
    assert super_checked["BigScience OpenRAIL-M (모델 가중치)"] is True
    assert super_checked["MIT (샘플 코드)"] is False


def test_main_branch_warns(tmp_path: Path) -> None:
    raw = {
        "schema_version": 1,
        "catalog_version": "t",
        "engines": [
            {
                "id": "x",
                "display_name": "X",
                "version": "1",
                "runtime": "onnx",
                "assets": [
                    {
                        "dest": "a.bin",
                        "sha256": "ab" * 32,
                        "size": 1,
                        "urls": ["https://huggingface.co/org/model/resolve/main/a.bin"],
                    }
                ],
            }
        ],
    }
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    catalog = load_catalog(path)
    assert any("main" in w.message for w in catalog.warnings)


def test_missing_field(tmp_path: Path) -> None:
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"engines": [{"id": "x"}]}), encoding="utf-8")
    with pytest.raises(CatalogError):
        load_catalog(path)
