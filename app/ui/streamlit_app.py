"""Aplikasi operator QC. Jalankan dari root repo: streamlit run app/ui/streamlit_app.py

Mode B (utama):    mengirim masukan ke API (API_URL di .streamlit/secrets.toml).
Mode A (cadangan): kalau API_URL kosong atau API tidak bisa dihubungi, model dimuat dan dijalankan di sini.
"""
import logging
import os
import sys
from pathlib import Path

import requests
import streamlit as st
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api import model as penyimpan_model  # noqa: E402
from app.api.model import LABEL  # noqa: E402
from app.api.schemas import BAHAN, MESIN, MasukanSiklus, terjemahkan_galat  # noqa: E402
from src.features import SUHU_STANDAR  # noqa: E402

# log prediksi Mode A tampil di log server Streamlit (Manage app > Logs)
_log_prediksi = logging.getLogger("app.api.prediksi")
_log_prediksi.setLevel(logging.INFO)
if not _log_prediksi.handlers and not logging.getLogger().handlers:
    _penangan = logging.StreamHandler()
    _penangan.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    _log_prediksi.addHandler(_penangan)

TIMEOUT_DETIK = 60  # hosting gratis bisa "tidur" dan butuh waktu untuk bangun (cold start)


def ambil_api_url() -> str:
    try:
        url = st.secrets.get("API_URL", "")
    except Exception:  # file secrets.toml tidak ada
        url = ""
    return (url or os.getenv("API_URL", "")).rstrip("/")


API_URL = ambil_api_url()


@st.cache_resource
def model_lokal():
    """Mode A: dimuat sekali saja, lalu dipakai ulang di setiap klik."""
    return penyimpan_model.muat()


def periksa(data: dict) -> tuple[str, object]:
    """Mengembalikan (jenis, isi). jenis: 'B' / 'A' (berhasil), 'galat_masukan', atau 'gagal'."""
    # periksa di sini dulu, supaya pesan salah isi langsung muncul tanpa menunggu API
    try:
        masukan = MasukanSiklus(**data)
    except ValidationError as e:
        return "galat_masukan", terjemahkan_galat(e.errors())

    if API_URL:
        try:
            r = requests.post(f"{API_URL}/predict", json=data, timeout=TIMEOUT_DETIK)
            if r.status_code == 200:
                return "B", r.json()
            if r.status_code == 422:
                return "galat_masukan", r.json()["detail"]
            # 503 atau 500: API hidup tetapi tidak bisa memprediksi, jadi pindah ke Mode A
        except (requests.RequestException, ValueError):
            pass  # API mati, timeout, atau jawabannya bukan JSON: pindah ke Mode A

    m = model_lokal()
    if not m.siap:
        return "gagal", None
    return "A", penyimpan_model.prediksi(masukan.model_dump(), m)


@st.cache_data(ttl=300, show_spinner=False)
def ambil_metadata() -> dict | None:
    if API_URL:
        try:
            r = requests.get(f"{API_URL}/metadata", timeout=10)
            if r.status_code == 200:
                return r.json()
        except requests.RequestException:
            pass
    m = model_lokal()
    return m.metadata if m.siap else None


def persen(x: float) -> str:
    """0.105 -> '10,5%'"""
    return f"{x:.1%}".replace(".", ",")


def isian_angka(kolom, minimal, maksimal, awal, langkah, opsional=False, kunci=None, format_angka=None):
    """number_input dengan batas yang sama dengan batas keras API. Kolom opsional diberi centang 'belum diukur'."""
    nama, satuan = LABEL[kolom]
    kunci = kunci or kolom
    belum = False
    if opsional:
        belum = st.checkbox(f"{nama} belum diukur", key=f"kosong_{kunci}")
    nilai = st.number_input(f"{nama} ({satuan})", min_value=minimal, max_value=maksimal, value=awal,
                            step=langkah, format=format_angka, disabled=belum, key=kunci)
    return None if belum else nilai


# ---------------- tampilan ----------------

st.set_page_config(page_title="QC Injection Molding", page_icon="🏭", layout="centered")
st.title("Pemeriksaan Cacat Injection Molding")
st.caption("Isi parameter satu siklus produksi, lalu tekan **Periksa** untuk melihat peluang cacat dan saran.")

mesin = st.selectbox("Mesin", MESIN)
bahan = st.selectbox("Bahan", BAHAN, help="Mengganti bahan akan mengisi suhu sesuai standar bahan itu.")
leleh_standar, cetakan_standar = SUHU_STANDAR[bahan]

# kunci memakai nama bahan, jadi saat bahan diganti, kotak suhu dibuat ulang dengan nilai standar bahan baru
data = {
    "mesin": mesin,
    "bahan": bahan,
    "suhu_leleh_C": isian_angka("suhu_leleh_C", 150.0, 400.0, float(leleh_standar), 1.0,
                                kunci=f"leleh_{bahan}", format_angka="%.1f"),
    "suhu_cetakan_C": isian_angka("suhu_cetakan_C", 0.0, 150.0, float(cetakan_standar), 1.0,
                                  kunci=f"cetakan_{bahan}", format_angka="%.1f"),
    "kecepatan_injeksi_mm_s": isian_angka("kecepatan_injeksi_mm_s", 0.1, 300.0, 80.0, 1.0, format_angka="%.1f"),
    "tekanan_injeksi_bar": isian_angka("tekanan_injeksi_bar", 1.0, 2500.0, 900.0, 10.0, opsional=True,
                                       format_angka="%.0f"),
    "waktu_pendinginan_s": isian_angka("waktu_pendinginan_s", 0.1, 120.0, 15.0, 0.5, opsional=True,
                                       format_angka="%.1f"),
    "waktu_siklus_s": isian_angka("waktu_siklus_s", 0.1, 300.0, 30.0, 0.5, opsional=True, format_angka="%.1f"),
    "kelembaban_bahan_pct": isian_angka("kelembaban_bahan_pct", 0.0, 5.0, 0.05, 0.01, opsional=True,
                                        format_angka="%.3f"),
}

if st.button("Periksa", type="primary", width="stretch"):
    try:
        with st.spinner("Menghitung... (kalau server baru bangun, bisa sampai satu menit)"):
            jenis, isi = periksa(data)
    except Exception:
        jenis, isi = "gagal", None

    if jenis == "galat_masukan":
        st.error("Ada isian yang perlu diperbaiki:")
        for g in isi:
            nama = LABEL.get(g["kolom"], (g["kolom"],))[0]
            st.markdown(f"- **{nama}**: {g['pesan']}")

    elif jenis == "gagal":
        st.error("Model belum tersedia dan API tidak bisa dihubungi. Coba lagi beberapa saat lagi.")

    else:
        hasil = isi
        peluang = hasil["probabilitas_cacat"]
        st.divider()
        st.metric("Peluang cacat", persen(peluang))
        st.progress(min(max(peluang, 0.0), 1.0))

        batas = persen(hasil["threshold"])
        if hasil["keputusan"] == "PISAHKAN":
            st.error(f"### PISAHKAN\nPeluang cacat {persen(peluang)}, sama atau di atas batas {batas}. "
                     f"Sisihkan komponen ini untuk diperiksa.")
        else:
            st.success(f"### LOLOS\nPeluang cacat {persen(peluang)}, di bawah batas {batas}.")

        if hasil["saran"]:
            st.subheader("Saran tindakan")
            for s in hasil["saran"]:
                st.markdown(f"- {s}")

        for p in hasil["peringatan"]:
            st.warning(p)

        if jenis == "B":
            st.caption(f"Mode B: dihitung oleh API · model {hasil['versi_model']}")
        elif API_URL:
            st.caption(f"Mode A: dihitung langsung di aplikasi karena API tidak bisa dihubungi · "
                       f"model {hasil['versi_model']}")
        else:
            st.caption(f"Mode A: dihitung langsung di aplikasi · model {hasil['versi_model']}")

with st.expander("Tentang model"):
    md = ambil_metadata()
    if not md:
        st.write("Informasi model belum tersedia.")
    else:
        metrik = md.get("metrik", {})
        biaya = md.get("biaya", {})

        def rupiah(x):
            return f"Rp{x:,}".replace(",", ".") if x is not None else "-"

        def angka(x):
            return f"{x:g}".replace(".", ",") if isinstance(x, (int, float)) else "-"

        baris = [
            f"- **Model:** {md.get('nama_model', '-')} (versi {md.get('versi_model', '-')}, "
            f"dilatih {md.get('tanggal_latih', '-')})",
            f"- **Batas keputusan (threshold):** {angka(md.get('threshold'))}. {md.get('alasan_threshold', '')}",
            f"- **Biaya:** komponen cacat yang lolos {rupiah(biaya.get('fn'))}, komponen bagus yang disisihkan "
            f"{rupiah(biaya.get('fp'))}. Karena itu model sengaja dibuat mudah curiga.",
            f"- **PR-AUC:** validation {angka(metrik.get('pr_auc_validation'))}, "
            f"test {angka(metrik.get('pr_auc_test'))} (baseline test {angka(metrik.get('baseline_pr_auc_test'))})",
        ]
        if isinstance(metrik.get("recall_test"), (int, float)):
            baris.append(f"- **Di data test:** menangkap {metrik['recall_test']:.0%} komponen cacat (recall). "
                         f"Dari komponen yang disisihkan, {metrik.get('precision_test', 0):.0%} memang cacat "
                         f"(precision).")
        st.markdown("\n".join(baris))
