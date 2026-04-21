from aiohttp.web import StreamResponse, HTTPServiceUnavailable, HTTPUnauthorized
from aiohttp.web_request import Request
from aiohttp import ClientSession
from typing import Awaitable, Callable
from functools import wraps
from src.settings import settings
from authentication_types.models import User
import jwt

def get_user(handler: Callable[[Request], Awaitable[StreamResponse]]):
    @wraps(handler)
    async def wrapper(request: Request):
        jwt = request.headers.get("Authorization", "")
        if not jwt:
            raise HTTPUnauthorized(body='{"error": "missing jwt"}')
        payload = decode_access_token(jwt)
        request["user"] = User(user_id=payload["sub"], pseudo=payload["pseudo"])
        return await handler(request)
    
    return wrapper


def decode_access_token(token: str) -> dict:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Invalid token type")
    return payload