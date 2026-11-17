from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings

from app.routers.auth import router as auth_router
from app.routers.anexos import router as anexos_router
from app.routers.anotacoes import router as anotacoes_router
from app.routers.calendario_academico import router as calendario_academico_router
from app.routers.avaliacoes import router as avaliacoes_router
from app.routers.docentes import router as docentes_router
from app.routers.disciplinas import router as disciplinas_router
from app.routers.eventos import router as eventos_router
from app.routers.frequencias import router as frequencias_router
from app.routers.horarios_aula import router as horarios_aula_router
from app.routers.semestres import router as semestres_router


app = FastAPI(title="HUB SCHOOL API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth_router)
app.include_router(anexos_router)
app.include_router(anotacoes_router)
app.include_router(calendario_academico_router)
app.include_router(avaliacoes_router)
app.include_router(docentes_router)
app.include_router(disciplinas_router)
app.include_router(eventos_router)
app.include_router(frequencias_router)
app.include_router(horarios_aula_router)
app.include_router(semestres_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
