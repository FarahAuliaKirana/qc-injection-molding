"""Fitur dari pengetahuan proses injection molding.

Dipakai saat pelatihan (notebook) dan saat prediksi (API), supaya cara menghitungnya selalu sama.
File ini dibuat oleh notebook bagian 5. Jika ingin mengubahnya, ubah di notebook lalu jalankan ulang.
"""
import pandas as pd

# suhu standar dari tim proses: (suhu leleh, suhu cetakan) dalam °C
SUHU_STANDAR = {"PP": (230, 40), "ABS": (240, 60), "PC": (300, 90)}
# bahan yang menyerap air dari udara
BAHAN_HIGROSKOPIS = {"ABS", "PC"}
# mulai tekanan ini persentase cacat sudah normal (notebook bagian 4.4)
TEKANAN_CUKUP_BAR = 850

KOLOM_ANGKA = ["suhu_leleh_C", "suhu_cetakan_C", "tekanan_injeksi_bar", "kecepatan_injeksi_mm_s",
               "waktu_pendinginan_s", "waktu_siklus_s", "kelembaban_bahan_pct"]
FITUR_BARU = ["selisih_leleh", "selisih_cetakan", "abs_selisih_leleh", "abs_selisih_cetakan",
              "kelembaban_higroskopis", "kekurangan_tekanan"]


def buat_fitur(df: pd.DataFrame) -> pd.DataFrame:
    """Menerima DataFrame berisi 9 kolom masukan, mengembalikan salinan dengan kolom FITUR_BARU."""
    df = df.copy()
    # nilai kosong dari API bisa berupa None, dan kolomnya jadi bertipe object. Ubah ke float supaya menjadi NaN.
    df[KOLOM_ANGKA] = df[KOLOM_ANGKA].astype(float)
    leleh_standar = df["bahan"].map({b: s[0] for b, s in SUHU_STANDAR.items()})
    cetakan_standar = df["bahan"].map({b: s[1] for b, s in SUHU_STANDAR.items()})

    df["selisih_leleh"] = df["suhu_leleh_C"] - leleh_standar
    df["selisih_cetakan"] = df["suhu_cetakan_C"] - cetakan_standar
    df["abs_selisih_leleh"] = df["selisih_leleh"].abs()
    df["abs_selisih_cetakan"] = df["selisih_cetakan"].abs()

    # PP tidak menyerap air, jadi kelembabannya dianggap 0, termasuk jika kosong
    higroskopis = df["bahan"].isin(BAHAN_HIGROSKOPIS)
    df["kelembaban_higroskopis"] = df["kelembaban_bahan_pct"]
    df.loc[~higroskopis, "kelembaban_higroskopis"] = 0.0

    # seberapa jauh tekanan di bawah batas cukup. Tekanan yang kosong tetap kosong.
    df["kekurangan_tekanan"] = (TEKANAN_CUKUP_BAR - df["tekanan_injeksi_bar"]).clip(lower=0)
    return df
