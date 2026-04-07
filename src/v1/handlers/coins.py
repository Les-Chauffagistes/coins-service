from authentication_types.models import User
from aiohttp.web import Request, json_response, HTTPOk, HTTPNoContent
from init import app
from prisma import Prisma
from src.middlewares.get_user import get_user
from src.middlewares.authorization import require_auth

from ..services.balance import get_balance
from ..schemas.transactionPayload import CreditPayload, BurnPayload
from ..app import routes
from ..services.claim import claim as claim_service, get_claimable
from ..services.transaction import burn_wallet, credit_wallet


@routes.get("/claim")
@require_auth
@get_user
async def claim(request: Request):
    prisma: Prisma = app["prisma"]
    user: User = request["user"]
    currency = request.query.get("currency", "")
    if not currency:
        return json_response({"error": "missing currency"}, status=400)
    
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
    payload = await request.json()
    parsed_payload = CreditPayload(**payload)
    async with prisma.tx() as tx:
        await credit_wallet(tx, user, parsed_payload.amount, parsed_payload.currency, parsed_payload.source, parsed_payload.reason)
    return HTTPOk()

@routes.delete("/burn")
@require_auth
@get_user
async def burn(request: Request):
    prisma: Prisma = app["prisma"]
    user: User = request["user"]
    payload = await request.json()
    parsed_payload = BurnPayload(**payload)
    async with prisma.tx() as tx:
        await burn_wallet(tx, user, parsed_payload.amount, parsed_payload.currency, parsed_payload.destination, parsed_payload.reason)
    
    return HTTPNoContent()

@routes.get("/balance")
@require_auth
@get_user
async def balance(request: Request):
    prisma: Prisma = app["prisma"]
    user: User = request["user"]
    currency = request.query.get("currency")
    if not currency:
        return json_response({"error": "missing currency"}, status=400)
    
    balance = await get_balance(prisma, user, currency)
    return json_response({"balance": balance})

@routes.get("/claimable")
@require_auth
@get_user
async def claimable(request: Request):
    prisma: Prisma = app["prisma"]
    user: User = request["user"]
    currency = request.query.get("currency")
    if not currency:
        return json_response({"error": "missing currency"}, status=400)

    claimable = await get_claimable(prisma, user, currency)
    return json_response({"claimable": claimable})
