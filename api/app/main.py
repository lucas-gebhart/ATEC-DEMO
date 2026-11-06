from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers import core, industry, planning, scheduling

app = FastAPI(title="ATEC Test Planning Demo")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
for r in (core, industry, planning, scheduling):
    app.include_router(r.router)


@app.on_event("startup")
def _startup():
    init_db()
