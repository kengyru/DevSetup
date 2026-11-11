"""DRF exception handling.

Validation errors and authentication failures keep their normal shape so
clients can show useful messages. Unexpected errors are logged with a
traceback and returned as a generic 500 response: no stack trace, SQL
fragment or request body ever reaches the client.
"""

import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger("api.errors")


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        return response

    logger.exception("Unhandled API exception")

    return Response(
        {"detail": "A server error occurred."},
        status=500,
    )
