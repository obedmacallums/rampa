"""Uniform API error envelope: {"error": {"code", "message_key", "detail"}}.

API responses never embed user-facing prose or stack traces (FR-008, SC-003);
the frontend resolves ``message_key`` through its i18n catalogs.
"""

from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class ApiError(exceptions.APIException):
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, code: str, message_key: str | None = None, detail: dict | None = None,
                 status_code: int | None = None):
        self.code = code
        self.message_key = message_key or f"errors.{code}"
        self.extra_detail = detail or {}
        if status_code is not None:
            self.status_code = status_code
        super().__init__(detail=code)


def envelope(code: str, message_key: str, detail: dict | None = None) -> dict:
    return {"error": {"code": code, "message_key": message_key, "detail": detail or {}}}


def api_exception_handler(exc, context):
    if isinstance(exc, ApiError):
        return Response(
            envelope(exc.code, exc.message_key, exc.extra_detail), status=exc.status_code
        )
    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    # SessionAuthentication yields 403 for anonymous users; the contract says 401.
    if isinstance(exc, exceptions.NotAuthenticated):
        response.status_code = status.HTTP_401_UNAUTHORIZED
    code = {
        status.HTTP_401_UNAUTHORIZED: "not_authenticated",
        status.HTTP_403_FORBIDDEN: "forbidden",
        status.HTTP_404_NOT_FOUND: "not_found",
        status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
    }.get(response.status_code, "invalid_request")
    response.data = envelope(code, f"errors.{code}")
    return response
