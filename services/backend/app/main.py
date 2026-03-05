import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name, version='0.1.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.middleware('http')
async def correlation_middleware(request: Request, call_next):
    correlation_id = request.headers.get('x-correlation-id') or str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers['x-correlation-id'] = correlation_id
    return response


@app.middleware('http')
async def logging_middleware(request: Request, call_next):
    correlation_id = getattr(request.state, 'correlation_id', '')
    logger.info(
        'request.start',
        extra={
            'correlation_id': correlation_id,
            'tenant_id': request.headers.get('x-tenant-id', ''),
            'method': request.method,
            'path': request.url.path,
        },
    )
    response = await call_next(request)
    logger.info(
        'request.end',
        extra={
            'correlation_id': correlation_id,
            'tenant_id': request.headers.get('x-tenant-id', ''),
            'status_code': response.status_code,
            'path': request.url.path,
        },
    )
    return response


app.include_router(api_router, prefix=settings.api_v1_prefix)
Instrumentator().instrument(app).expose(app, endpoint='/metrics')


@app.on_event('startup')
async def startup() -> None:
    logger.info('app.startup', extra={'correlation_id': '', 'tenant_id': ''})
