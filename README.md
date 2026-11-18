# [Nama proyek] · Tim [nama tim]

**Kasus:** 01 · Pengendalian Mutu *Injection Molding* · **Aplikasi:** [tautan aplikasi] · **Video:** [tautan video]

| Anggota | NIM | Bagian yang dikerjakan |
|---|---|---|
| [nama] | [NIM] | [misalnya EDA dan pembersihan data] |
| [nama] | [NIM] | [misalnya model dan evaluasi] |
| [nama] | [NIM] | [misalnya API dan aplikasi] |

## Masalah dan pengguna

Di pabrik komponen plastik klien, komponen cacat baru ketahuan saat inspeksi visual di akhir shift, sehingga ratusan
komponen bisa telanjur cacat sebelum pengaturan mesin diperbaiki. Model ini membantu operator mesin di lantai produksi.
Operator memasukkan bahan, mesin, dan parameter proses dari satu siklus cetak, lalu model memberikan probabilitas bahwa
komponen tersebut cacat beserta saran tindakan. Dengan begitu, komponen yang berisiko bisa langsung dipisahkan dan
pengaturan mesin bisa segera diperbaiki.

## Data dan pembersihan

Data mentah berisi 25.350 siklus cetak dari empat mesin selama Maret sampai Juni 2026, dengan sekitar 8% komponen cacat.

| Masalah yang ditemukan | Jumlah baris | Cara menangani |
|---|---|---|
| Penulisan `bahan` tidak seragam (`PP `, `P.P`, `pp`, `Abs`, …) | 761 | Dirapikan menjadi PP, ABS, atau PC |
| Penulisan `shift` tidak seragam (`SIANG`, `malam `, `Pagi`) | 506 | Diubah ke huruf kecil dan spasi dihapus |
| Baris duplikat persis | 350 | Dihapus dengan `drop_duplicates` sebelum data dibagi |
| `suhu_leleh_C` IM-04 tercatat dalam °F (10 sampai 23 April 2026) | 579 | Dikonversi ke °C dengan (°F − 32) × 5/9 |
| `tekanan_injeksi_bar` = 0 | 125 | Diubah menjadi NaN dan diisi median data train di pipeline |
| `waktu_siklus_s` = −1 | 75 | Diubah menjadi NaN dan diisi median data train di pipeline |
| `kelembaban_bahan_pct` kosong | 1.000 | Diisi median data train di pipeline |
| `waktu_pendinginan_s` kosong | 250 | Diisi median data train di pipeline |
| Nilai ekstrem (IQR per bahan) | 1.725 | Dibiarkan karena baris ekstrem jauh lebih sering cacat |
| Label `shift` tidak cocok dengan jam di `waktu_produksi` | 25.000 | Tidak dipakai sebagai masukan dan ditanyakan ke klien |

## Hasil

| Model | PR-AUC *validation* | PR-AUC *test* |
|---|---|---|
| *Baseline*: regresi logistik (fitur asli) | | |
| [model final] | | |

*Threshold* yang dipakai: [angka], karena [alasan bisnis].

## Cara menjalankan

```bash
python -m venv .venv
source .venv/bin/activate               # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt     # library aplikasi + notebook + tes

uvicorn app.api.main:app --reload       # API
streamlit run app/ui/streamlit_app.py   # aplikasi
```

Notebook `notebooks/qc_injection_molding.ipynb` dijalankan dengan kernel dari `.venv`. Notebook ini membaca
`data/raw.csv` dan menghasilkan `data/bersih.csv`, `src/features.py`, serta isi folder `artifacts/`.

## Struktur repositori

```
notebooks/      notebook dari EDA sampai penyimpanan model
data/           data mentah (data bersih dibuat ulang oleh notebook)
src/features.py fungsi pembuat fitur, dipakai saat pelatihan dan saat prediksi
artifacts/      model.joblib + metadata.json
app/            API (FastAPI) dan antarmuka (Streamlit)
```

## Keterbatasan

[Dalam kondisi apa model ini tidak dapat dipercaya? Data apa yang belum tersedia?]

## Daftar periksa sebelum dikumpulkan

- [ ] Repositori bersifat publik dan setiap anggota memiliki *commit*
- [ ] *Notebook* dapat dijalankan ulang dari awal sampai akhir tanpa galat
- [ ] *Baseline* wajib dilaporkan dan dibandingkan
- [ ] Data *test* hanya dibuka satu kali, di akhir
- [ ] `artifacts/metadata.json` berisi versi model, fitur masukan, *threshold*, dan metrik
- [ ] Aplikasi dapat dibuka orang lain melalui tautan, termasuk dari ponsel
- [ ] Aplikasi tidak berhenti mendadak ketika menerima masukan yang tidak wajar
- [ ] Laporan paling banyak 6 halaman dan video paling lama 5 menit
