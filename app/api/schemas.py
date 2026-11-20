"""Bentuk data yang masuk dan keluar dari API (PRD §11.1–11.2).

MasukanSiklus memeriksa setiap permintaan sebelum sampai ke model. Kalau ada yang salah, FastAPI menjawab 422
dan model tidak disentuh. terjemahkan_galat mengubah pesan galat Pydantic menjadi bahasa Indonesia.
"""
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from src.features import SUHU_STANDAR

MESIN = ["IM-01", "IM-02", "IM-03", "IM-04"]
BAHAN = list(SUHU_STANDAR)  # PP, ABS, PC

CONTOH_MASUKAN = {
    "mesin": "IM-03",
    "bahan": "ABS",
    "suhu_leleh_C": 262.0,
    "suhu_cetakan_C": 61.5,
    "tekanan_injeksi_bar": 905,
    "kecepatan_injeksi_mm_s": 80.2,
    "waktu_pendinginan_s": 17.5,
    "waktu_siklus_s": 31.0,
    "kelembaban_bahan_pct": 0.18,
}


class MasukanSiklus(BaseModel):
    # forbid: kolom yang salah ketik ditolak, bukan diam-diam diabaikan
    # allow_inf_nan=False: NaN dan Infinity di JSON ditolak
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False,
                              json_schema_extra={"examples": [CONTOH_MASUKAN]})

    # urutan kolom sama dengan fitur_masukan di metadata.json
    mesin: str
    bahan: str
    suhu_leleh_C: float = Field(ge=150)  # batas atas 400 diperiksa di cek_fahrenheit
    suhu_cetakan_C: float = Field(ge=0, le=150)
    tekanan_injeksi_bar: float | None = Field(default=None, gt=0, le=2500)
    kecepatan_injeksi_mm_s: float = Field(gt=0, le=300)
    waktu_pendinginan_s: float | None = Field(default=None, gt=0, le=120)
    waktu_siklus_s: float | None = Field(default=None, gt=0, le=300)
    kelembaban_bahan_pct: float | None = Field(default=None, ge=0, le=5)

    @field_validator("mesin", mode="before")
    @classmethod
    def normalkan_mesin(cls, nilai):
        # "im-3", "IM03", "im_03", " IM-03 " -> "IM-03"
        cocok = re.fullmatch(r"IM[-_ ]?0?([1-4])", str(nilai).upper().strip())
        if not cocok:
            raise ValueError(f"'{nilai}' tidak dikenal. Pilih salah satu: {', '.join(MESIN)}")
        return f"IM-0{cocok.group(1)}"

    @field_validator("bahan", mode="before")
    @classmethod
    def normalkan_bahan(cls, nilai):
        # "pp", "P.P", " Abs " -> "PP", "PP", "ABS"
        teks = str(nilai).upper().replace(".", "").strip()
        if teks not in BAHAN:
            raise ValueError(f"'{nilai}' tidak dikenal. Pilih salah satu: {', '.join(BAHAN)}")
        return teks

    @field_validator("suhu_leleh_C")
    @classmethod
    def cek_fahrenheit(cls, nilai):
        if nilai > 400:
            raise ValueError(f"{nilai:g} di atas 400. Kemungkinan tercatat dalam °F. Konversikan ke °C.")
        return nilai

    @field_validator("waktu_siklus_s")
    @classmethod
    def cek_siklus_lebih_lama(cls, nilai, info: ValidationInfo):
        # info.data berisi kolom yang sudah lolos diperiksa sebelumnya (waktu_pendinginan_s ada di atas)
        pendinginan = info.data.get("waktu_pendinginan_s")
        if nilai is not None and pendinginan is not None and nilai <= pendinginan:
            raise ValueError(f"harus lebih besar dari waktu_pendinginan_s ({pendinginan:g} detik), "
                             f"karena pendinginan adalah bagian dari satu siklus")
        return nilai


class HasilPrediksi(BaseModel):
    probabilitas_cacat: float = Field(ge=0, le=1)
    keputusan: Literal["PISAHKAN", "LOLOS"]
    threshold: float
    saran: list[str]
    peringatan: list[str]
    versi_model: str


# Pydantic memberi "jenis" galat (type) dan angka batasnya (ctx). Kita pakai itu untuk menyusun kalimat sendiri.
_PESAN = {
    "missing": lambda e: "wajib diisi",
    "extra_forbidden": lambda e: "kolom tidak dikenal",
    "float_parsing": lambda e: f"harus berupa angka, bukan '{e['input']}'",
    "float_type": lambda e: "harus berupa angka",
    "finite_number": lambda e: "harus berupa angka biasa, bukan NaN atau tak hingga",
    "string_type": lambda e: "harus berupa teks",
    "greater_than": lambda e: f"harus lebih dari {e['ctx']['gt']:g}",
    "greater_than_equal": lambda e: f"minimal {e['ctx']['ge']:g}",
    "less_than": lambda e: f"harus kurang dari {e['ctx']['lt']:g}",
    "less_than_equal": lambda e: f"maksimal {e['ctx']['le']:g}",
    "value_error": lambda e: str(e["ctx"]["error"]),
    "json_invalid": lambda e: "format JSON tidak valid",
    "model_attributes_type": lambda e: "masukan harus berupa objek JSON berisi kolom-kolom siklus",
    "dict_type": lambda e: "masukan harus berupa objek JSON berisi kolom-kolom siklus",
}


def terjemahkan_galat(daftar_galat) -> list[dict]:
    """[{type, loc, msg, ...}] dari Pydantic -> [{"kolom": ..., "pesan": ...}] berbahasa Indonesia."""
    hasil = []
    for e in daftar_galat:
        # loc dari FastAPI diawali "body", misalnya ("body", "suhu_leleh_C")
        lokasi = [str(x) for x in e["loc"] if x != "body"]
        kolom = ".".join(lokasi) or "masukan"
        if e["type"] == "json_invalid":
            kolom = "masukan"  # loc-nya posisi karakter yang rusak, bukan nama kolom
        if kolom == "masukan" and e["type"] == "missing":
            pesan = "data masukan kosong. Kirim objek JSON berisi kolom-kolom siklus."
        else:
            ubah = _PESAN.get(e["type"])
            pesan = ubah(e) if ubah else e["msg"]
        hasil.append({"kolom": kolom, "pesan": pesan})
    return hasil
