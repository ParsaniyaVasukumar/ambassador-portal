from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import data
from app.config import BASE_DIR, INDIA_GEOJSON_URL, REFRESH_INTERVAL_MINUTES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ambassador_portal")

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    data.refresh()
    scheduler.add_job(data.refresh, "interval", minutes=REFRESH_INTERVAL_MINUTES, id="refresh_job")
    scheduler.start()
    logger.info("Scheduler started: refreshing every %s minute(s)", REFRESH_INTERVAL_MINUTES)
    yield
    scheduler.shutdown()


app = FastAPI(title="On2Cook Ambassador Portal", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


def _cache_meta() -> dict:
    cache = data.get_cache()
    return {
        "source": cache.source,
        "last_refreshed": cache.last_refreshed.isoformat() if cache.last_refreshed else None,
        "last_error": cache.last_error,
    }


@app.get("/api/debug")
async def api_debug():
    cache = data.get_cache()
    return JSONResponse({
        "raw_columns": cache.raw_columns,
        "raw_row_count": cache.raw_row_count,
        "raw_sample": cache.raw_sample,
        "cleaned_row_count": len(cache.df) if cache.df is not None else 0,
        **_cache_meta(),
    })


@app.get("/")
async def home(request: Request):
    summary = data.get_analytics_summary()
    return templates.TemplateResponse("index.html", {
        "request": request, "summary": summary, "meta": _cache_meta(),
        "geojson_url": INDIA_GEOJSON_URL, "active_page": "home",
    })


@app.get("/roster")
async def roster(request: Request):
    states = sorted({row["state_display"] for row in data.get_ambassadors() if row["state_display"]})
    profiles = data.get_profiles()
    return templates.TemplateResponse("roster.html", {
        "request": request, "states": states, "profiles": profiles,
        "meta": _cache_meta(), "active_page": "roster",
    })


@app.get("/analytics")
async def analytics(request: Request):
    summary = data.get_analytics_summary()
    return templates.TemplateResponse("analytics.html", {
        "request": request, "summary": summary, "meta": _cache_meta(), "active_page": "analytics",
    })


@app.get("/api/ambassadors")
async def api_ambassadors(search: str = "", state: str = "", city: str = "",
                           profile: str = "", sort_by: str = "sr_no", sort_dir: str = "asc"):
    return JSONResponse(data.get_ambassadors(
        search=search, state=state, city=city, profile=profile,
        sort_by=sort_by, sort_dir=sort_dir,
    ))


@app.get("/api/states")
async def api_states():
    return JSONResponse(data.get_states_summary())


@app.get("/api/cities")
async def api_cities(state: str = Query(...)):
    return JSONResponse(data.get_cities_for_state(state))


@app.get("/api/analytics/summary")
async def api_analytics_summary():
    return JSONResponse(data.get_analytics_summary())


@app.get("/api/meta")
async def api_meta():
    return JSONResponse(_cache_meta())


@app.post("/api/refresh")
async def api_refresh():
    cache = data.refresh(force=True)
    return JSONResponse({
        "ok": cache.last_error is None,
        "rows": len(cache.df) if cache.df is not None else 0,
        **_cache_meta(),
    })