"""Aturan saran tindakan S1–S8 (PRD §12).

Saran berasal dari temuan EDA notebook bagian 4, bukan dari model, supaya mudah dijelaskan ke operator.
Suhu standar, bahan higroskopis, dan batas tekanan diambil dari src.features, jadi hanya ada satu sumber angka.
"""
from src.features import BAHAN_HIGROSKOPIS, SUHU_STANDAR, TEKANAN_CUKUP_BAR

BATAS_SELISIH_SUHU = 10        # S1, S2: di atas ini saran muncul (°C)
TARGET_SELISIH_SUHU = 5        # target: ±5 °C dari standar
BATAS_KELEMBABAN_TINGGI = 0.15  # S3 (%)
BATAS_KELEMBABAN_WASPADA = 0.10  # S4 (%), juga target pengeringan
BATAS_PENDINGINAN = 13          # S6 (detik)
MESIN_BERMASALAH = "IM-03"      # S7


def _angka(x: float) -> str:
    """262.0 -> '262', 0.18 -> '0,18' (koma desimal)."""
    return f"{x:g}".replace(".", ",")


def _persen(x: float) -> str:
    """Kelembaban minimal 2 angka di belakang koma: 0.2 -> '0,20', 0.088 -> '0,088'."""
    teks = f"{x:.2f}" if round(x, 2) == x else f"{x:g}"
    return teks.replace(".", ",")


def _saran_suhu(nama: str, nilai: float, standar: float, bahan: str) -> str | None:
    selisih = nilai - standar
    if abs(selisih) <= BATAS_SELISIH_SUHU:
        return None
    arah, tindakan = ("di atas", "Turunkan") if selisih > 0 else ("di bawah", "Naikkan")
    rendah, tinggi = standar - TARGET_SELISIH_SUHU, standar + TARGET_SELISIH_SUHU
    return (f"{nama} {_angka(abs(selisih))} °C {arah} standar {bahan} ({_angka(standar)} °C). "
            f"{tindakan} ke {_angka(rendah)}–{_angka(tinggi)} °C.")


def pilih_aturan(masukan: dict, keputusan: str) -> list[tuple[str, str]]:
    """Mengembalikan [(kode, kalimat saran), ...] yang sudah diurutkan. Prioritas (S3) tampil paling atas."""
    bahan = masukan["bahan"]
    leleh_standar, cetakan_standar = SUHU_STANDAR[bahan]
    kelembaban = masukan.get("kelembaban_bahan_pct")
    tekanan = masukan.get("tekanan_injeksi_bar")
    pendinginan = masukan.get("waktu_pendinginan_s")

    terpicu = []  # (prioritas, kode, kalimat); prioritas 0 tampil lebih dulu

    teks = _saran_suhu("Suhu leleh", masukan["suhu_leleh_C"], leleh_standar, bahan)
    if teks:
        terpicu.append((1, "S1", teks))

    teks = _saran_suhu("Suhu cetakan", masukan["suhu_cetakan_C"], cetakan_standar, bahan)
    if teks:
        terpicu.append((1, "S2", teks))

    if bahan in BAHAN_HIGROSKOPIS and kelembaban is not None:
        if kelembaban > BATAS_KELEMBABAN_TINGGI:
            terpicu.append((0, "S3", f"Prioritas: kelembaban {bahan} {_persen(kelembaban)}% sudah di atas batas "
                                     f"{_persen(BATAS_KELEMBABAN_TINGGI)}%. Keringkan bahan sampai di bawah "
                                     f"{_persen(BATAS_KELEMBABAN_WASPADA)}% sebelum dicetak."))
        elif kelembaban >= BATAS_KELEMBABAN_WASPADA:
            terpicu.append((1, "S4", f"Kelembaban {bahan} {_persen(kelembaban)}% mulai tinggi. "
                                     f"Pertimbangkan pengeringan tambahan sampai di bawah "
                                     f"{_persen(BATAS_KELEMBABAN_WASPADA)}%."))

    if tekanan is not None and tekanan < TEKANAN_CUKUP_BAR:
        terpicu.append((1, "S5", f"Tekanan injeksi {_angka(tekanan)} bar di bawah {TEKANAN_CUKUP_BAR} bar. "
                                 f"Naikkan ke {TEKANAN_CUKUP_BAR} bar atau lebih."))

    if pendinginan is not None and pendinginan < BATAS_PENDINGINAN:
        terpicu.append((1, "S6", f"Waktu pendinginan {_angka(pendinginan)} detik terlalu singkat. "
                                 f"Perpanjang ke {BATAS_PENDINGINAN} detik atau lebih."))

    if masukan["mesin"] == MESIN_BERMASALAH:
        terpicu.append((1, "S7", f"{MESIN_BERMASALAH} tercatat lebih sering cacat dan cenderung 6 °C lebih panas. "
                                 f"Laporkan ke bagian perawatan."))

    # S8 hanya kalau tidak ada aturan parameter proses (S1–S6) yang menjelaskan keputusan PISAHKAN
    ada_penyebab = any(kode in {"S1", "S2", "S3", "S4", "S5", "S6"} for _, kode, _ in terpicu)
    if keputusan == "PISAHKAN" and not ada_penyebab:
        terpicu.append((1, "S8", "Parameter proses tampak normal, tetapi model memperkirakan risiko cacat. "
                                 "Pisahkan dan periksa manual, kemungkinan ada faktor lain."))

    terpicu.sort(key=lambda t: (t[0], t[1]))
    return [(kode, kalimat) for _, kode, kalimat in terpicu]


def buat_saran(masukan: dict, keputusan: str) -> list[str]:
    return [kalimat for _, kalimat in pilih_aturan(masukan, keputusan)]
