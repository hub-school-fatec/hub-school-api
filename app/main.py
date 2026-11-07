from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import install_error_handlers
from app.routers.academic import router as academic_router
from app.routers.planning import router as planning_router

from app.routers.auth import router as auth_router
from app.routers.health import router as health_router


app = FastAPI(title="HUB SCHOOL API")
install_error_handlers(app)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                   allow_methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
                   allow_headers=['Authorization', 'Content-Type'])

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(academic_router)
app.include_router(planning_router)
