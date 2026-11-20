"""Perlengkapan bersama untuk semua tes.

Tes memakai model dummy yang dibuat ulang di folder sementara, bukan artifacts/ milik Farah,
supaya hasil tes tidak bergantung pada model yang sedang dipakai atau sedang diganti.
"""
import os

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.schemas import CONTOH_MASUKAN
from scripts.buat_model_dummy import buat_model_dummy


@pytest.fixture(scope="session")
def folder_dummy(tmp_path_factory):
    # dilatih sekali untuk seluruh sesi tes (sekitar 3 detik)
    return buat_model_dummy(tmp_path_factory.mktemp("model_dummy"))


def _klien(folder):
    lama = os.environ.get("MODEL_DIR")
    os.environ["MODEL_DIR"] = str(folder)
    try:
        # raise_server_exceptions=False: galat 500 dijawab seperti di server sungguhan, bukan dilempar ke tes
        with TestClient(app, raise_server_exceptions=False) as klien:
            yield klien
    finally:
        if lama is None:
            os.environ.pop("MODEL_DIR", None)
        else:
            os.environ["MODEL_DIR"] = lama


@pytest.fixture
def klien(folder_dummy):
    """API yang sudah memuat model dummy."""
    yield from _klien(folder_dummy)


@pytest.fixture
def klien_tanpa_model(tmp_path):
    """API dengan MODEL_DIR yang kosong, untuk menguji jawaban 503."""
    yield from _klien(tmp_path / "tidak_ada")


@pytest.fixture
def contoh():
    """Contoh masukan valid dari PRD §11.1. Salinan baru setiap tes, jadi aman diubah."""
    return dict(CONTOH_MASUKAN)
