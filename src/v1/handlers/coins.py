from json import JSONDecodeError
from aiohttp.web import Request, json_response, HTTPOk, HTTPNoContent
from prisma import Prisma
from prisma.errors import DataError
from pydantic import ValidationError
from chauff_cmn.models import User
from chauff_cmn.logging import logger as log
from init import app
from src.middlewares.get_user import get_user
from src.middlewares.authorization import require_auth

from ..schemas.transactionPayload import CreditPayload, BurnPayload, TransferPayload
from ..app import routes
from ..services.balance import get_balance, get_balance_by_id
from ..services.claim import claim as claim_service, get_claimable, ClaimConflictError
from ..services.transaction import burn as burn_service, credit as credit_service, transfer as transfer_service
from ..services.idempotency import get_idempotency_status
from ..errors import missing_currency_error, json_parse_error, bad_request_error, currency_not_found_error


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

    except ClaimConflictError:
        return json_response({"error": "concurrent claim, retry"}, status=409)

    except ValueError:
        return currency_not_found_error

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
        return json_parse_error
    except ValidationError:
        log.exception("")
        return bad_request_error

    existing_status = await get_idempotency_status(prisma, parsed_payload.idempotencyKey, int(user.user_id))
    if existing_status is not None:
        return json_response(None, status=existing_status)

    await credit_service(prisma, user, parsed_payload.amount, parsed_payload.currency, parsed_payload.source, parsed_payload.reason, parsed_payload.idempotencyKey, 200)
    return HTTPOk()

@routes.delete("/burn")
@require_auth
@get_user
async def burn(request: Request):
    prisma: Prisma = app["prisma"]
    user: User = request["user"]
    try:
        payload = await request.json()
        parsed_payload = BurnPayload(**payload)
    except JSONDecodeError:
        return json_parse_error
    except ValidationError as e:
        log.error(e)
        return bad_request_error

    existing_status = await get_idempotency_status(prisma, parsed_payload.idempotencyKey, int(user.user_id))
    if existing_status is not None:
        return json_response(None, status=existing_status)

    try:
        await burn_service(prisma, user, parsed_payload.amount, parsed_payload.currency, parsed_payload.destination, parsed_payload.reason, parsed_payload.idempotencyKey, 204)
    except DataError:
        return json_response({"error": "insufficient balance"}, status=400)
    except ValueError as e:
        return json_response({"error": str(e)}, status=400)
    return HTTPNoContent()

@routes.post("/transfer")
@require_auth
# Pas de @get_user ici volontairement : contrairement aux autres routes, la
# source et la destination sont des comptes passés explicitement dans le
# payload (peuvent être des pseudo-comptes système, sans JWT propre — ex.
# escrow:battle:{battleId} qui vit sous l'userId négatif -battleId). Seul un
# appelant de confiance (X-Api-Key) peut faire bouger des fonds sans être
# l'utilisateur concerné.
async def transfer(request: Request):
    prisma: Prisma = app["prisma"]
    try:
        payload = await request.json()
        parsed_payload = TransferPayload(**payload)
    except JSONDecodeError:
        return json_parse_error
    except ValidationError as e:
        log.error(e)
        return bad_request_error

    existing_status = await get_idempotency_status(prisma, parsed_payload.idempotencyKey, parsed_payload.fromUserId)
    if existing_status is not None:
        return json_response(None, status=existing_status)

    try:
        await transfer_service(
            prisma,
            parsed_payload.fromUserId,
            parsed_payload.toUserId,
            parsed_payload.amount,
            parsed_payload.currency,
            parsed_payload.reason,
            parsed_payload.idempotencyKey,
            204,
        )
    except DataError as e:
        log.error(e)
        return json_response({"error": "insufficient balance"}, status=400)
    except ValueError as e:
        log.error(e)
        return json_response({"error": str(e)}, status=400)
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

@routes.get("/internal/balance")
@require_auth
# Pas de @get_user : lecture seule pour un appelant de confiance (X-Api-Key)
# qui veut le solde d'un compte arbitraire, y compris un compte système sans
# JWT (ex. escrow:battle:{battleId}). Sert à la réconciliation périodique
# côté hash-contenders (Phase 6) : vérifier qu'un escrow de bataille réglée
# est bien retombé à zéro, hors du chemin critique.
async def internal_balance(request: Request):
    prisma: Prisma = app["prisma"]
    currency = request.query.get("currency", "")
    user_id = request.query.get("userId", "")
    if not currency:
        return missing_currency_error
    if not user_id:
        return json_response({"error": "missing userId"}, status=400)

    try:
        balance = await get_balance_by_id(prisma, int(user_id), currency)
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
