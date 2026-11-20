"""src/features.py dari Farah (PRD §11.5): tidak mengubah masukan, tahan NaN, dan nilainya sesuai hitungan manual."""
import math

import pandas as pd

from src.features import FITUR_BARU, TEKANAN_CUKUP_BAR, buat_fitur


def data_contoh():
    return pd.DataFrame([
        {"mesin": "IM-01", "bahan": "ABS", "suhu_leleh_C": 262.0, "suhu_cetakan_C": 55.0,
         "tekanan_injeksi_bar": 800.0, "kecepatan_injeksi_mm_s": 80.0, "waktu_pendinginan_s": 15.0,
         "waktu_siklus_s": 30.0, "kelembaban_bahan_pct": 0.18},
        {"mesin": "IM-02", "bahan": "PP", "suhu_leleh_C": 225.0, "suhu_cetakan_C": 40.0,
         "tekanan_injeksi_bar": None, "kecepatan_injeksi_mm_s": 80.0, "waktu_pendinginan_s": None,
         "waktu_siklus_s": None, "kelembaban_bahan_pct": None},
    ])


def test_tidak_mengubah_masukan():
    df = data_contoh()
    salinan = df.copy()
    buat_fitur(df)
    pd.testing.assert_frame_equal(df, salinan)


def test_menambah_semua_fitur_baru_tanpa_mengubah_jumlah_baris():
    hasil = buat_fitur(data_contoh())
    assert len(hasil) == 2
    assert set(FITUR_BARU) <= set(hasil.columns)


def test_nilai_sesuai_hitungan_manual():
    abs_, pp = buat_fitur(data_contoh()).to_dict("records")
    # ABS: standar leleh 240, cetakan 60
    assert abs_["selisih_leleh"] == 22
    assert abs_["abs_selisih_cetakan"] == 5
    assert abs_["kelembaban_higroskopis"] == 0.18
    assert abs_["kekurangan_tekanan"] == TEKANAN_CUKUP_BAR - 800
    # PP: standar leleh 230
    assert pp["selisih_leleh"] == -5
    assert pp["abs_selisih_leleh"] == 5


def test_tahan_nan():
    pp = buat_fitur(data_contoh()).iloc[1]
    assert pp["kelembaban_higroskopis"] == 0  # PP dianggap 0 walau kosong
    assert math.isnan(pp["kekurangan_tekanan"])  # tekanan kosong tetap kosong


def test_menerima_none_dari_api():
    # API mengirim None, bukan NaN. Kolomnya bisa bertipe object.
    df = data_contoh().astype(object)
    hasil = buat_fitur(df)
    assert math.isnan(hasil.iloc[1]["kekurangan_tekanan"])
