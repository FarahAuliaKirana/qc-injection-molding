"""Aplikasi Streamlit dijalankan tanpa peramban (AppTest): Mode A, isian salah, dan tidak pernah ada traceback."""
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app" / "ui" / "streamlit_app.py")


@pytest.fixture
def aplikasi(folder_dummy, monkeypatch):
    """Aplikasi dengan model lokal dummy. API_URL diisi di tiap tes."""
    monkeypatch.setenv("MODEL_DIR", str(folder_dummy))
    monkeypatch.delenv("API_URL", raising=False)
    st.cache_resource.clear()
    st.cache_data.clear()

    def jalankan(api_url=""):
        at = AppTest.from_file(APP, default_timeout=60)
        at.secrets["API_URL"] = api_url
        return at.run()

    return jalankan


def teks_halaman(at):
    bagian = [e.value for e in at.markdown] + [e.value for e in at.caption]
    bagian += [e.value for e in at.error] + [e.value for e in at.success] + [e.value for e in at.warning]
    return "\n".join(str(b) for b in bagian)


def test_halaman_terbuka_tanpa_galat(aplikasi):
    at = aplikasi()
    assert not at.exception
    assert at.title[0].value == "Pemeriksaan Cacat Injection Molding"


@pytest.mark.parametrize("api_url", ["", "http://127.0.0.1:9"])  # kosong, atau API mati
def test_mode_a_saat_api_tidak_ada(aplikasi, api_url):
    at = aplikasi(api_url)
    at.button[0].click().run()
    assert not at.exception
    assert len(at.metric) == 1
    assert "Mode A" in teks_halaman(at)


def test_ganti_bahan_mengubah_suhu_standar(aplikasi):
    at = aplikasi()
    at.selectbox[1].set_value("PC").run()
    assert at.number_input(key="leleh_PC").value == 300
    assert at.number_input(key="cetakan_PC").value == 90


def test_isian_salah_ditampilkan_per_kolom(aplikasi):
    at = aplikasi()
    at.number_input(key="waktu_pendinginan_s").set_value(20.0)
    at.number_input(key="waktu_siklus_s").set_value(10.0)
    at.button[0].click().run()
    assert not at.exception
    assert len(at.metric) == 0
    assert "Waktu siklus" in teks_halaman(at)


def test_belum_diukur_memberi_peringatan(aplikasi):
    at = aplikasi()
    at.checkbox(key="kosong_kelembaban_bahan_pct").check()
    at.button[0].click().run()
    assert not at.exception
    assert "Kelembaban bahan tidak diisi" in teks_halaman(at)


def test_model_tidak_ada_tanpa_traceback(aplikasi, monkeypatch, tmp_path):
    at = aplikasi()
    monkeypatch.setenv("MODEL_DIR", str(tmp_path / "tidak_ada"))
    st.cache_resource.clear()
    at.button[0].click().run()
    assert not at.exception
    assert "Model belum tersedia" in teks_halaman(at)
