from json import JSONDecodeError

from authentication_types.models import User
from aiohttp.web import Request, json_response, HTTPOk, HTTPNoContent
from prisma.errors import DataError
from pydantic import ValidationError
from init import app, log
from prisma import Prisma
from src.middlewares.get_user import get_user
from src.middlewares.authorization import require_auth

from ..services.balance import get_balance
from ..schemas.transactionPayload import CreditPayload, BurnPayload
from ..app import routes
from ..services.claim import claim as claim_service, get_claimable
from ..services.transaction import burn_wallet, credit_wallet
from ..services.idempotency import get_idempotency_status, store_idempotency_key
from ..errors import missing_currency_error

@routes.get("/claim")
@require_auth
@get_user
async def claim(request: Request):
    prisma: Prisma = app["prisma"]
    user: User = request["user"]
    currency = request.query.get("currency", "")
    if not currency:
        return missing_currency_error
    
    try:
        claimed = await claim_service(prisma, user, currency)
        return json_response({"claimed": claimed})
    
    except ValueError:
        return json_response({"error": "currency not found"}, status=400)

@routes.post("/credit")
@require_auth
@get_user
async def credit(request: Request):
    prisma: Prisma = app["prisma"]
    user: User = request["user"]
    try:
        payload = await request.json()
        parsed_payload = CreditPayload(**payload)
    except JSONDecodeError:
        return json_response({"error": "pasing json failed"}, status=400)
    except ValidationError:
        log.error()
        return json_response({"error": "bad request"}, status=400)

    existing_status = await get_idempotency_status(prisma, parsed_payload.idempotencyKey, int(user.user_id))
    if existing_status is not None:
        return json_response(None, status=existing_status)

    async with prisma.tx() as tx:
        await credit_wallet(tx, user, parsed_payload.amount, parsed_payload.currency, parsed_payload.source, parsed_payload.reason)
        await store_idempotency_key(tx, parsed_payload.idempotencyKey, int(user.user_id), 200)
    return HTTPOk()

@routes.delete("/burn")
@require_auth
@get_user
async def burn(request: Request):
    prisma: Prisma = app["prisma"]
    user: User = request["user"]
    payload = await request.json()
    parsed_payload = BurnPayload(**payload)

    existing_status = await get_idempotency_status(prisma, parsed_payload.idempotencyKey, int(user.user_id))
    if existing_status is not None:
        return json_response(None, status=existing_status)

    try:
        async with prisma.tx() as tx:
            await burn_wallet(tx, user, parsed_payload.amount, parsed_payload.currency, parsed_payload.destination, parsed_payload.reason)
            await store_idempotency_key(tx, parsed_payload.idempotencyKey, int(user.user_id), 204)
    except DataError:
        return json_response({"error": "insufficient balance"}, status=400)
    return HTTPNoContent()

@routes.get("/balance")
@require_auth
@get_user
async def balance(request: Request):
    prisma: Prisma = app["prisma"]
    user: User = request["user"]
    currency = request.query.get("currency")
    if not currency:
        return missing_currency_error
    
    try:
        balance = await get_balance(prisma, user, currency)
    
    except ValueError:
        return json_response({"balance": 0})
    return json_response({"balance": balance})

@routes.get("/claimable")
@require_auth
@get_user
async def claimable(request: Request):
    prisma: Prisma = app["prisma"]
    user: User = request["user"]
    currency = request.query.get("currency")
    if not currency:
        return missing_currency_error

    claimable = await get_claimable(prisma, user, currency)
    return json_response({"claimable": claimable})
