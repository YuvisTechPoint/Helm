"""Cross-cutting HTTP behaviour: request IDs, optional API keys, consistent errors."""

from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.errors import BudgetExceeded, ConfigurationError, InvalidTransition, IsolationError, MissingCredentials, PolicyDenied, ProviderUnavailable


OPEN_PATHS = {"/health", "/ready", "/live", "/metrics", "/docs", "/openapi.json", "/redoc"}


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_key: str = "", engine_version: str = "2027.1", default_tenant: str = "local"):
        super().__init__(app)
        self.api_key = api_key
        self.engine_version = engine_version
        self.default_tenant = default_tenant

    async def dispatch(self, request: Request, call_next):
        from core.context import bind_context

        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        if self.api_key and request.url.path not in OPEN_PATHS and not request.url.path.startswith("/webhooks"):
            presented = request.headers.get("x-api-key", "")
            if presented != self.api_key:
                return JSONResponse(
                    {"detail": "invalid or missing API key", "request_id": request_id},
                    status_code=401,
                    headers={"X-Request-Id": request_id, "X-Engine-Version": self.engine_version},
                )
        from core.observability import metrics

        metrics().inc("http_requests")
        with bind_context(tenant=self.default_tenant, request=request_id):
            try:
                response = await call_next(request)
            except Exception:
                metrics().inc("http_errors")
                raise
        if response.status_code >= 500:
            metrics().inc("http_5xx")
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Engine-Version"] = self.engine_version
        return response


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(PolicyDenied)
    async def policy_denied(_request: Request, exc: PolicyDenied):
        return JSONResponse({"detail": str(exc), "code": "policy_denied"}, status_code=409)

    @app.exception_handler(InvalidTransition)
    async def invalid_transition(_request: Request, exc: InvalidTransition):
        return JSONResponse({"detail": str(exc), "code": "conflict"}, status_code=409)

    @app.exception_handler(BudgetExceeded)
    async def budget_exceeded(_request: Request, exc: BudgetExceeded):
        return JSONResponse({"detail": str(exc), "code": "budget_exceeded"}, status_code=409)

    @app.exception_handler(IsolationError)
    async def isolation(_request: Request, exc: IsolationError):
        return JSONResponse({"detail": str(exc), "code": "isolation"}, status_code=403)

    @app.exception_handler(MissingCredentials)
    async def missing_credentials(_request: Request, exc: MissingCredentials):
        return JSONResponse({"detail": str(exc), "code": "configuration_error"}, status_code=503)

    @app.exception_handler(ProviderUnavailable)
    async def provider_unavailable(_request: Request, exc: ProviderUnavailable):
        return JSONResponse({"detail": str(exc), "code": "provider_error"}, status_code=503)

    @app.exception_handler(ConfigurationError)
    async def configuration_error(_request: Request, exc: ConfigurationError):
        return JSONResponse({"detail": str(exc), "code": "configuration_error"}, status_code=503)

def paginate(rows: list, limit: int = 50, offset: int = 0) -> dict:
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))
    return {"items": rows[offset : offset + limit], "total": len(rows), "limit": limit, "offset": offset}
