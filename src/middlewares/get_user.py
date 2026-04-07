from aiohttp.web import StreamResponse, HTTPServiceUnavailable, HTTPUnauthorized
from aiohttp.web_request import Request
from aiohttp import ClientSession
from typing import Awaitable, Callable
from functools import wraps
from src.settings import settings
from authentication_types.models import User

def get_user(handler: Callable[[Request], Awaitable[StreamResponse]]):
    @wraps(handler)
    async def wrapper(request: Request):
        jwt = request.headers.get("Authorization", "")
        if not jwt:
            raise HTTPUnauthorized(body='{"error": "missing jwt"}')
        async with ClientSession(settings.auth_service_url, headers={"Authorization": jwt}) as session:
            async with session.get("/me") as req:
                if req.status != 200:
                    raise HTTPServiceUnavailable(body='{"error": "auth failed"}')
                user = User(**await req.json())
                request["user"] = user
                return await handler(request)
    
    return wrapper
