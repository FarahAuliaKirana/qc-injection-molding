"""Kasus uji API T1–T13 (PRD §18), ditambah beberapa kasus pelengkap."""
import json
from pathlib import Path

import pytest

from app.api import main
from app.api import model as penyimpan_model

KUNCI_HASIL = {"probabilitas_cacat", "keputusan", "threshold", "saran", "peringatan", "versi_model"}


def kolom_galat(r):
    return [g["kolom"] for g in r.json()["detail"]]


def pesan_galat(r):
    return " ".join(g["pesan"] for g in r.json()["detail"])


# ---------- endpoint dasar ----------

def test_health(klien):
    r = klien.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "versi_model": "0.0.0-dummy"}


def test_beranda_diarahkan_ke_docs(klien):
    r = klien.get("/", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"] == "/docs"


def test_metadata_tanpa_detail_internal(klien):
    r = klien.get("/metadata")
    assert r.status_code == 200
    data = r.json()
    assert {"versi_model", "threshold", "metrik", "fitur_masukan"} <= set(data)
    assert "versi_library" not in data


# ---------- T1–T3: masukan valid ----------

def test_t1_contoh_lengkap(klien, contoh):
    r = klien.post("/predict", json=contoh)
    assert r.status_code == 200
    hasil = r.json()
    assert set(hasil) == KUNCI_HASIL
    assert 0 <= hasil["probabilitas_cacat"] <= 1
    assert hasil["keputusan"] in ("PISAHKAN", "LOLOS")
    assert hasil["versi_model"] == "0.0.0-dummy"
    assert isinstance(hasil["saran"], list) and isinstance(hasil["peringatan"], list)


def test_keputusan_sesuai_threshold(klien, contoh):
    hasil = klien.post("/predict", json=contoh).json()
    harus = "PISAHKAN" if hasil["probabilitas_cacat"] >= hasil["threshold"] else "LOLOS"
    assert hasil["keputusan"] == harus


@pytest.mark.parametrize("cara", ["null", "tidak_dikirim"])
def test_t2_kolom_opsional_kosong(klien, contoh, cara):
    if cara == "null":
        contoh["tekanan_injeksi_bar"] = None
        contoh["kelembaban_bahan_pct"] = None
    else:
        del contoh["tekanan_injeksi_bar"], contoh["kelembaban_bahan_pct"]
    r = klien.post("/predict", json=contoh)
    assert r.status_code == 200
    peringatan = " ".join(r.json()["peringatan"])
    assert "Tekanan injeksi" in peringatan
    assert "Kelembaban bahan" in peringatan


def test_t2_semua_kolom_opsional_kosong(klien, contoh):
    for kolom in ("tekanan_injeksi_bar", "waktu_pendinginan_s", "waktu_siklus_s", "kelembaban_bahan_pct"):
        contoh[kolom] = None
    r = klien.post("/predict", json=contoh)
    assert r.status_code == 200
    assert len(r.json()["peringatan"]) == 4


@pytest.mark.parametrize("tulisan, harus", [("pp", "PP"), ("P.P", "PP"), (" Abs ", "ABS"), ("pc", "PC")])
def test_t3_bahan_dinormalkan(klien, contoh, tulisan, harus):
    contoh.update(bahan=tulisan, kelembaban_bahan_pct=0.2)
    r = klien.post("/predict", json=contoh)
    assert r.status_code == 200
    # S3 hanya untuk ABS dan PC, jadi muncul tidaknya S3 membuktikan bahan dibaca dengan benar
    ada_s3 = any("Prioritas" in s for s in r.json()["saran"])
    assert ada_s3 == (harus in ("ABS", "PC"))


@pytest.mark.parametrize("tulisan", ["im-3", "IM03", " im_03 ", "IM-03"])
def test_t3_mesin_dinormalkan(klien, contoh, tulisan):
    contoh["mesin"] = tulisan
    r = klien.post("/predict", json=contoh)
    assert r.status_code == 200
    assert any(s.startswith("IM-03") for s in r.json()["saran"])


# ---------- T4–T9: masukan tidak valid ----------

def test_t4_kategori_tidak_dikenal(klien, contoh):
    contoh.update(bahan="XYZ", mesin="IM-09")
    r = klien.post("/predict", json=contoh)
    assert r.status_code == 422
    assert set(kolom_galat(r)) == {"bahan", "mesin"}
    assert "PP, ABS, PC" in pesan_galat(r)
    assert "IM-01, IM-02, IM-03, IM-04" in pesan_galat(r)


def test_t5_suhu_fahrenheit(klien, contoh):
    contoh["suhu_leleh_C"] = 615
    r = klien.post("/predict", json=contoh)
    assert r.status_code == 422
    assert kolom_galat(r) == ["suhu_leleh_C"]
    assert "°F" in pesan_galat(r)


@pytest.mark.parametrize("kolom, nilai", [
    ("tekanan_injeksi_bar", 0),
    ("waktu_siklus_s", -1),
    ("suhu_leleh_C", 100),
    ("suhu_cetakan_C", 151),
    ("kecepatan_injeksi_mm_s", 301),
    ("kelembaban_bahan_pct", 6),
])
def test_t6_di_luar_batas_keras(klien, contoh, kolom, nilai):
    contoh[kolom] = nilai
    r = klien.post("/predict", json=contoh)
    assert r.status_code == 422
    assert kolom_galat(r) == [kolom]


@pytest.mark.parametrize("siklus", [15, 17.5])
def test_t7_siklus_tidak_lebih_lama_dari_pendinginan(klien, contoh, siklus):
    contoh.update(waktu_pendinginan_s=17.5, waktu_siklus_s=siklus)
    r = klien.post("/predict", json=contoh)
    assert r.status_code == 422
    assert kolom_galat(r) == ["waktu_siklus_s"]


def test_t8_teks_di_kolom_angka(klien, contoh):
    contoh["suhu_cetakan_C"] = "dua ratus"
    r = klien.post("/predict", json=contoh)
    assert r.status_code == 422
    assert "harus berupa angka" in pesan_galat(r)


def test_t9_kolom_wajib_tidak_dikirim(klien, contoh):
    del contoh["bahan"]
    r = klien.post("/predict", json=contoh)
    assert r.status_code == 422
    assert kolom_galat(r) == ["bahan"]
    assert "wajib diisi" in pesan_galat(r)


@pytest.mark.parametrize("body", [b"", b"{suhu", b"[1, 2]"])
def test_t9_body_kosong_atau_rusak(klien, body):
    r = klien.post("/predict", content=body, headers={"content-type": "application/json"})
    assert r.status_code == 422
    assert kolom_galat(r) == ["masukan"]


def test_kolom_salah_ketik_ditolak(klien, contoh):
    contoh["kelembaban"] = 0.1
    r = klien.post("/predict", json=contoh)
    assert r.status_code == 422
    assert kolom_galat(r) == ["kelembaban"]


# ---------- T10–T13 ----------

def test_t10_di_luar_rentang_data_latih(klien, contoh):
    contoh["tekanan_injeksi_bar"] = 2000  # di bawah batas keras 2.500, tetapi di atas data latih
    r = klien.post("/predict", json=contoh)
    assert r.status_code == 200
    assert any("di luar rentang data latih" in p for p in r.json()["peringatan"])


def test_t11_model_tidak_ada(klien_tanpa_model, contoh):
    for r in (klien_tanpa_model.get("/health"), klien_tanpa_model.get("/metadata"),
              klien_tanpa_model.post("/predict", json=contoh)):
        assert r.status_code == 503
        assert r.json() == {"detail": "Model belum tersedia."}


def test_t11_masukan_salah_tetap_422_walau_model_tidak_ada(klien_tanpa_model, contoh):
    contoh["suhu_leleh_C"] = 615
    assert klien_tanpa_model.post("/predict", json=contoh).status_code == 422


def test_t12_kelembaban_abs_tinggi_memicu_s3(klien, contoh):
    contoh.update(bahan="ABS", kelembaban_bahan_pct=0.20)
    saran = klien.post("/predict", json=contoh).json()["saran"]
    assert saran[0].startswith("Prioritas")
    assert "0,20%" in saran[0]


def test_t13_prediksi_dicatat_di_log(klien, contoh, caplog):
    caplog.set_level("INFO", logger="app.api.prediksi")
    hasil = klien.post("/predict", json=contoh).json()
    catatan = [json.loads(c.getMessage()) for c in caplog.records if c.name == "app.api.prediksi"]
    assert len(catatan) == 1
    assert {"waktu", "masukan", "hasil"} <= set(catatan[0])
    assert catatan[0]["masukan"]["bahan"] == "ABS"
    assert catatan[0]["hasil"] == hasil


# ---------- galat tak terduga ----------

def test_galat_tak_terduga_jadi_500_tanpa_detail(klien, contoh, monkeypatch):
    def rusak(*args):
        raise RuntimeError("rahasia internal")

    monkeypatch.setattr(main.penyimpan_model, "prediksi", rusak)
    r = klien.post("/predict", json=contoh)
    assert r.status_code == 500
    assert r.json() == {"detail": "Terjadi kesalahan di server."}
    assert "rahasia" not in r.text


# ---------- model asli di artifacts/ ----------

ARTIFACTS = Path(__file__).resolve().parents[1] / "artifacts"


@pytest.mark.skipif(not (ARTIFACTS / "model.joblib").exists(), reason="artifacts/ belum ada")
def test_model_di_artifacts_bisa_dipakai(contoh):
    """Memastikan model dari Farah cocok dengan API: bisa dimuat, dan bisa memprediksi dengan atau tanpa NaN."""
    m = penyimpan_model.muat(ARTIFACTS)
    assert m.siap, m.galat
    for masukan in (contoh, {**contoh, "tekanan_injeksi_bar": None, "kelembaban_bahan_pct": None}):
        hasil = penyimpan_model.prediksi(masukan, m)
        assert 0 <= hasil["probabilitas_cacat"] <= 1
