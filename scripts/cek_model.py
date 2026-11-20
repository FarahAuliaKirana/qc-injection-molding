"""Memeriksa model di artifacts/ sebelum dipakai API (PRD B9). Jalankan setiap kali Farah mengganti model.

Yang diperiksa:
1. model.joblib dan metadata.json bisa dimuat, dan semua kunci wajib (§11.7) ada.
2. Seluruh data/bersih.csv bisa diprediksi, termasuk baris dengan nilai kosong.
3. Peluangnya masuk akal: baris cacat rata-rata lebih tinggi daripada baris bagus.

Jalankan dari root repo:  python scripts/cek_model.py   (atau: python scripts/cek_model.py artifacts_dummy)
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.model import muat  # noqa: E402

KUNCI_WAJIB = {"versi_model", "tanggal_latih", "nama_model", "fitur_masukan", "kolom_opsional", "kategori",
               "rentang_data_latih", "threshold", "alasan_threshold", "biaya", "metrik", "versi_library"}


def cek(folder: str = "artifacts") -> bool:
    m = muat(folder)
    if not m.siap:
        print(f"GAGAL: model tidak bisa dimuat. {m.galat}")
        return False
    md = m.metadata
    print(f"Model {md['versi_model']}: {md['nama_model']} (threshold {md['threshold']})")

    kurang = KUNCI_WAJIB - set(md)
    if kurang:
        print(f"GAGAL: metadata.json tidak punya kunci {sorted(kurang)}")
        return False

    data = pd.read_csv(ROOT / "data" / "bersih.csv")
    peluang = m.model.predict_proba(data[md["fitur_masukan"]])[:, 1]
    data["peluang"] = peluang
    ada_kosong = data[md["kolom_opsional"]].isna().any(axis=1)

    rata_cacat = data.loc[data["cacat"] == 1, "peluang"].mean()
    rata_bagus = data.loc[data["cacat"] == 0, "peluang"].mean()
    pisahkan = (peluang >= md["threshold"]).mean()
    print(f"- {len(data):,} baris diprediksi, {ada_kosong.sum():,} di antaranya punya kolom kosong")
    print(f"- rata-rata peluang: baris cacat {rata_cacat:.3f}, baris bagus {rata_bagus:.3f}")
    print(f"- {pisahkan:.0%} baris akan diberi keputusan PISAHKAN")

    if not ((0 <= peluang) & (peluang <= 1)).all():
        print("GAGAL: ada peluang di luar 0–1")
        return False
    if rata_cacat <= rata_bagus:
        print("GAGAL: baris cacat tidak lebih berisiko daripada baris bagus")
        return False
    print("OK: model siap dipakai API")
    return True


if __name__ == "__main__":
    sys.exit(0 if cek(*sys.argv[1:2]) else 1)
