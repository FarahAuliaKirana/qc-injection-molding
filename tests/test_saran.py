"""Aturan saran S1–S8 (PRD §12): setiap aturan punya tes yang memicu dan tes yang tidak memicu."""
import pytest

from app.api.saran import buat_saran, pilih_aturan
from src.features import TEKANAN_CUKUP_BAR

# semua parameter di titik aman: tidak ada saran yang boleh muncul
NORMAL = {
    "mesin": "IM-01",
    "bahan": "ABS",
    "suhu_leleh_C": 240.0,
    "suhu_cetakan_C": 60.0,
    "tekanan_injeksi_bar": 900.0,
    "kecepatan_injeksi_mm_s": 80.0,
    "waktu_pendinginan_s": 15.0,
    "waktu_siklus_s": 30.0,
    "kelembaban_bahan_pct": 0.05,
}


def kode(perubahan=None, keputusan="LOLOS"):
    return [k for k, _ in pilih_aturan({**NORMAL, **(perubahan or {})}, keputusan)]


def test_parameter_normal_tanpa_saran():
    assert kode() == []
    assert buat_saran(NORMAL, "LOLOS") == []


@pytest.mark.parametrize("perubahan, harus_ada", [
    # S1 suhu leleh, standar ABS 240 °C, batas selisih 10 °C
    ({"suhu_leleh_C": 251}, True),
    ({"suhu_leleh_C": 229}, True),
    ({"suhu_leleh_C": 250}, False),
    ({"suhu_leleh_C": 230}, False),
])
def test_s1_suhu_leleh(perubahan, harus_ada):
    assert ("S1" in kode(perubahan)) == harus_ada


def test_s1_kalimat_memakai_angka_masukan():
    saran = buat_saran({**NORMAL, "suhu_leleh_C": 262}, "LOLOS")
    assert saran == ["Suhu leleh 22 °C di atas standar ABS (240 °C). Turunkan ke 235–245 °C."]


def test_s1_arah_naikkan_untuk_suhu_rendah():
    saran = buat_saran({**NORMAL, "bahan": "PC", "suhu_leleh_C": 280, "suhu_cetakan_C": 90}, "LOLOS")
    assert saran == ["Suhu leleh 20 °C di bawah standar PC (300 °C). Naikkan ke 295–305 °C."]


@pytest.mark.parametrize("perubahan, harus_ada", [
    ({"suhu_cetakan_C": 71}, True),
    ({"suhu_cetakan_C": 49}, True),
    ({"suhu_cetakan_C": 70}, False),
])
def test_s2_suhu_cetakan(perubahan, harus_ada):
    assert ("S2" in kode(perubahan)) == harus_ada


@pytest.mark.parametrize("perubahan, harus", [
    ({"kelembaban_bahan_pct": 0.20}, ["S3"]),
    ({"kelembaban_bahan_pct": 0.16, "bahan": "PC", "suhu_leleh_C": 300, "suhu_cetakan_C": 90}, ["S3"]),
    ({"kelembaban_bahan_pct": 0.15}, ["S4"]),
    ({"kelembaban_bahan_pct": 0.10}, ["S4"]),
    ({"kelembaban_bahan_pct": 0.09}, []),
    ({"kelembaban_bahan_pct": None}, []),
    # PP tidak menyerap air, jadi kelembaban tinggi tidak memicu saran
    ({"kelembaban_bahan_pct": 0.30, "bahan": "PP", "suhu_leleh_C": 230, "suhu_cetakan_C": 40}, []),
])
def test_s3_s4_kelembaban(perubahan, harus):
    assert kode(perubahan) == harus


@pytest.mark.parametrize("tekanan, harus_ada", [
    (TEKANAN_CUKUP_BAR - 1, True),
    (700, True),
    (TEKANAN_CUKUP_BAR, False),
    (None, False),
])
def test_s5_tekanan(tekanan, harus_ada):
    assert ("S5" in kode({"tekanan_injeksi_bar": tekanan})) == harus_ada


def test_s5_memakai_batas_dari_src_features():
    saran = buat_saran({**NORMAL, "tekanan_injeksi_bar": 720}, "LOLOS")
    assert saran == [f"Tekanan injeksi 720 bar di bawah {TEKANAN_CUKUP_BAR} bar. "
                     f"Naikkan ke {TEKANAN_CUKUP_BAR} bar atau lebih."]


@pytest.mark.parametrize("pendinginan, harus_ada", [(12.9, True), (9, True), (13, False), (None, False)])
def test_s6_pendinginan(pendinginan, harus_ada):
    assert ("S6" in kode({"waktu_pendinginan_s": pendinginan})) == harus_ada


@pytest.mark.parametrize("mesin, harus_ada", [("IM-03", True), ("IM-01", False), ("IM-04", False)])
def test_s7_mesin(mesin, harus_ada):
    assert ("S7" in kode({"mesin": mesin})) == harus_ada


def test_s8_pisahkan_tanpa_penyebab():
    assert kode(keputusan="PISAHKAN") == ["S8"]


def test_s8_tetap_muncul_walau_hanya_ada_s7():
    # S7 (mesin) bukan parameter proses, jadi tidak menjelaskan penyebab
    assert kode({"mesin": "IM-03"}, keputusan="PISAHKAN") == ["S7", "S8"]


def test_s8_tidak_muncul_jika_ada_penyebab():
    assert kode({"tekanan_injeksi_bar": 700}, keputusan="PISAHKAN") == ["S5"]


def test_s8_tidak_muncul_jika_lolos():
    assert kode(keputusan="LOLOS") == []


def test_urutan_prioritas_di_atas():
    semua = {"suhu_leleh_C": 262, "suhu_cetakan_C": 75, "kelembaban_bahan_pct": 0.2,
             "tekanan_injeksi_bar": 700, "waktu_pendinginan_s": 9, "mesin": "IM-03"}
    assert kode(semua) == ["S3", "S1", "S2", "S5", "S6", "S7"]
