"""Memuat model dan memakainya untuk prediksi.

muat():     membuka model.joblib dan metadata.json sekali saat API mulai. Folder dibaca dari variabel lingkungan
            MODEL_DIR (bawaan: artifacts). Kalau gagal, API tetap menyala dan menjawab 503, bukan berhenti.
prediksi(): dipakai oleh API (/predict) dan oleh Streamlit saat Mode A, supaya hasilnya selalu sama.
"""
import json
import logging
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import joblib
import pandas as pd

log = logging.getLogger(__name__)

# root repo: app/api/model.py -> naik dua folder
ROOT = Path(__file__).resolve().parents[2]

# pipeline final memakai src.features di dalamnya, jadi root repo harus bisa di-import
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.saran import buat_saran  # noqa: E402  (perlu sys.path di atas, karena saran memakai src.features)


@dataclass
class ModelTermuat:
    model: object | None = None
    metadata: dict | None = None
    galat: str | None = None

    @property
    def siap(self) -> bool:
        return self.model is not None and self.metadata is not None


def muat(folder: str | Path | None = None) -> ModelTermuat:
    folder = Path(folder or os.getenv("MODEL_DIR", "artifacts"))
    if not folder.is_absolute():
        folder = ROOT / folder

    try:
        model = joblib.load(folder / "model.joblib")
        metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    except Exception as e:
        log.error("Model gagal dimuat dari %s: %s", folder, e)
        return ModelTermuat(galat=f"{type(e).__name__}: {e}")

    log.info("Model %s dimuat dari %s", metadata.get("versi_model"), folder)
    return ModelTermuat(model=model, metadata=metadata)


LABEL = {
    "suhu_leleh_C": ("Suhu leleh", "°C"),
    "suhu_cetakan_C": ("Suhu cetakan", "°C"),
    "tekanan_injeksi_bar": ("Tekanan injeksi", "bar"),
    "kecepatan_injeksi_mm_s": ("Kecepatan injeksi", "mm/s"),
    "waktu_pendinginan_s": ("Waktu pendinginan", "detik"),
    "waktu_siklus_s": ("Waktu siklus", "detik"),
    "kelembaban_bahan_pct": ("Kelembaban bahan", "%"),
}


def _angka(x: float) -> str:
    return f"{x:g}".replace(".", ",")


def buat_peringatan(masukan: dict, metadata: dict) -> list[str]:
    """Kolom opsional yang kosong dan nilai di luar rentang data latih."""
    peringatan = []
    for kolom in metadata["kolom_opsional"]:
        if masukan.get(kolom) is None:
            nama = LABEL.get(kolom, (kolom,))[0]
            peringatan.append(f"{nama} tidak diisi. Model memakai nilai pengganti, jadi hasilnya kurang akurat.")

    for kolom, (bawah, atas) in metadata.get("rentang_data_latih", {}).items():
        nilai = masukan.get(kolom)
        if nilai is not None and not (bawah <= nilai <= atas):
            nama, satuan = LABEL.get(kolom, (kolom, ""))
            peringatan.append(f"{nama} {_angka(nilai)} {satuan} di luar rentang data latih "
                              f"({_angka(bawah)}–{_angka(atas)} {satuan}). Hasil untuk nilai ini kurang bisa "
                              f"dipercaya.")
    return peringatan


def prediksi(masukan: dict, m: ModelTermuat) -> dict:
    """masukan: dict 9 kolom yang sudah lolos MasukanSiklus. Mengembalikan dict berformat HasilPrediksi (§11.2)."""
    md = m.metadata
    # tabel satu baris, urutan kolom mengikuti metadata. None di kolom angka diubah menjadi NaN.
    baris = pd.DataFrame([{k: masukan.get(k) for k in md["fitur_masukan"]}])
    kolom_angka = [k for k in md["fitur_masukan"] if k not in md["kategori"]]
    baris[kolom_angka] = baris[kolom_angka].astype(float)

    peluang = float(m.model.predict_proba(baris)[0, 1])
    if not math.isfinite(peluang):
        raise ValueError(f"Model menghasilkan probabilitas tidak valid: {peluang}")

    threshold = float(md["threshold"])
    keputusan = "PISAHKAN" if peluang >= threshold else "LOLOS"
    return {
        "probabilitas_cacat": round(peluang, 4),
        "keputusan": keputusan,
        "threshold": threshold,
        "saran": buat_saran(masukan, keputusan),
        "peringatan": buat_peringatan(masukan, md),
        "versi_model": md["versi_model"],
    }
