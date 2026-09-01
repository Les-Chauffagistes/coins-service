from aiohttp.web import middleware, StreamResponse
from aiohttp.web_exceptions import HTTPException
from aiohttp.web_request import Request
from typing import Awaitable, Callable


@middleware
async def error_handler(request: Request, handler: Callable[[Request], Awaitable[StreamResponse]]) -> StreamResponse:
    import init as hs_init
    log = hs_init.log

    try:
        return await handler(request)

    except HTTPException:
        # Le log JSON structuré (méthode, chemin, statut, durée) est désormais
        # émis par chauff_cmn.logging.aiohttp.request_logging_middleware.
        log.exception("Request error")
        raise