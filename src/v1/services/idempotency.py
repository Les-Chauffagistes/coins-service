from prisma import Prisma


async def get_idempotency_status(prisma: Prisma, key: str, user_id: int) -> int | None:
    record = await prisma.idempotencykey.find_unique(
        where={"key_userId": {"key": key, "userId": user_id}}
    )
    return record.statusCode if record else None


async def store_idempotency_key(tx: Prisma, key: str, user_id: int, status_code: int):
    await tx.idempotencykey.create({
        "key": key,
        "userId": user_id,
        "statusCode": status_code,
    })
