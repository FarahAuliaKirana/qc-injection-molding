"""Aplikasi FastAPI. Jalankan dari root repo: uvicorn app.api.main:app --reload"""
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse

from app.api import model as penyimpan_model
from app.api.schemas import HasilPrediksi, MasukanSiklus, terjemahkan_galat

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app.api")
log_prediksi = logging.getLogger("app.api.prediksi")

def model_belum_ada() -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "Model belum tersedia."})


@asynccontextmanager
async def lifespan(app: FastAPI):
    # dijalankan sekali saat API mulai, sebelum menerima permintaan
    app.state.model = penyimpan_model.muat()
    yield


app = FastAPI(
    title="QC Injection Molding API",
    description="Memprediksi peluang cacat satu siklus injection molding dan memberi saran tindakan.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def masukan_tidak_valid(request: Request, exc: RequestValidationError):
    # ganti pesan 422 bawaan (bahasa Inggris) dengan daftar kolom dan pesan berbahasa Indonesia
    return JSONResponse(status_code=422, content={"detail": terjemahkan_galat(exc.errors())})


@app.exception_handler(Exception)
async def galat_tak_terduga(request: Request, exc: Exception):
    # detail galat hanya dicatat di log server, tidak dikirim ke pemakai
    log.exception("Galat tak terduga di %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Terjadi kesalahan di server."})


@app.get("/", include_in_schema=False)
def beranda():
    return RedirectResponse("/docs")


@app.get("/health")
def health(request: Request):
    m = request.app.state.model
    if not m.siap:
        return model_belum_ada()
    return {"status": "ok", "versi_model": m.metadata["versi_model"]}


@app.get("/metadata")
def metadata(request: Request):
    m = request.app.state.model
    if not m.siap:
        return model_belum_ada()
    # tanpa versi_library: itu detail internal server
    return {k: v for k, v in m.metadata.items() if k != "versi_library"}


@app.post("/predict", response_model=HasilPrediksi)
def predict(masukan: MasukanSiklus, request: Request):
    m = request.app.state.model
    if not m.siap:
        return model_belum_ada()

    data = masukan.model_dump()
    hasil = penyimpan_model.prediksi(data, m)
    log_prediksi.info(json.dumps({"waktu": datetime.now().isoformat(timespec="seconds"),
                                  "masukan": data, "hasil": hasil}, ensure_ascii=False))
    return hasil
