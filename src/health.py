from init import routes
from aiohttp.web import HTTPOk


@routes.get("/health")
async def health(r):
    return HTTPOk()