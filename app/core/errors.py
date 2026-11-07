from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import logging


class DomainError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError):
        return JSONResponse(status_code=exc.status, content={'detail': exc.detail})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Never echo tokens, free text or other submitted values in error responses.
        errors = [{'loc': list(e['loc']), 'type': e['type']} for e in exc.errors()]
        return JSONResponse(status_code=422, content={'detail': errors})

    @app.middleware('http')
    async def unexpected_error(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            # Do not let exception values/tracebacks containing credentials reach logs.
            logging.getLogger('hub_school').error('Falha interna na API; detalhes suprimidos.')
            return JSONResponse(status_code=500, content={'detail': 'Erro interno.'})
