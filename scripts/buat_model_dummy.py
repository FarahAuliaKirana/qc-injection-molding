"""Membuat model sementara (dummy) untuk pengujian API.

Hasilnya model.joblib dan metadata.json berformat sama dengan artifacts/ (PRD §11.6–11.7),
disimpan ke artifacts_dummy/ (tidak di-commit). Model ini tidak dipakai untuk prediksi sungguhan.

Jalankan dari root repo:  python scripts/buat_model_dummy.py
"""
import json
import platform
import sys
from datetime import date
from importlib.metadata import version
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.features import FITUR_BARU, KOLOM_ANGKA, buat_fitur  # noqa: E402

FITUR_MASUKAN = ["mesin", "bahan", "suhu_leleh_C", "suhu_cetakan_C", "tekanan_injeksi_bar",
                 "kecepatan_injeksi_mm_s", "waktu_pendinginan_s", "waktu_siklus_s", "kelembaban_bahan_pct"]
KOLOM_OPSIONAL = ["tekanan_injeksi_bar", "waktu_pendinginan_s", "waktu_siklus_s", "kelembaban_bahan_pct"]


def buat_model_dummy(folder: str | Path = ROOT / "artifacts_dummy") -> Path:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    data = pd.read_csv(ROOT / "data" / "bersih.csv")
    X, y = data[FITUR_MASUKAN], data["cacat"]

    pipeline = Pipeline([
        ("fitur", FunctionTransformer(buat_fitur)),
        ("siapkan", ColumnTransformer([
            ("angka", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), KOLOM_ANGKA + FITUR_BARU),
            ("kategori", OneHotEncoder(handle_unknown="ignore"), ["mesin", "bahan"]),
        ])),
        ("model", LogisticRegression(max_iter=1000)),
    ])
    pipeline.fit(X, y)

    angka = X.select_dtypes("number")
    metadata = {
        "versi_model": "0.0.0-dummy",
        "tanggal_latih": date.today().isoformat(),
        "nama_model": "Dummy: regresi logistik untuk pengujian API",
        "fitur_masukan": FITUR_MASUKAN,
        "kolom_opsional": KOLOM_OPSIONAL,
        "kategori": {"mesin": ["IM-01", "IM-02", "IM-03", "IM-04"], "bahan": ["PP", "ABS", "PC"]},
        "rentang_data_latih": {k: [round(float(angka[k].min()), 3), round(float(angka[k].max()), 3)]
                               for k in angka.columns},
        "threshold": 0.05,
        "alasan_threshold": "Dummy, disamakan dengan baseline. Bukan hasil perhitungan biaya.",
        "biaya": {"fn": 500000, "fp": 25000},
        "metrik": {"baseline_pr_auc_validation": None, "pr_auc_validation": None,
                   "pr_auc_test": None, "recall_test": None, "precision_test": None},
        "versi_library": {"python": platform.python_version(), "scikit-learn": version("scikit-learn"),
                          "pandas": version("pandas"), "numpy": version("numpy")},
    }

    joblib.dump(pipeline, folder / "model.joblib")
    (folder / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return folder


if __name__ == "__main__":
    print(f"Model dummy disimpan di {buat_model_dummy()}")
