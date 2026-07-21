from prisma import Prisma
import pytest_asyncio
import pytest
from src.modules.logger.logger import Logger
from dotenv import load_dotenv
import subprocess, os, sys
from shutil import which
from pathlib import Path
from testcontainers.postgres import PostgresContainer


load_dotenv(".env.test", override=True)


def _to_prisma_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+psycopg2://"):
        return database_url.replace("postgresql+psycopg2://", "postgresql://", 1)
    return database_url


def _resolve_prisma_cli() -> str:
    prisma = which("prisma")
    if prisma:
        return prisma

    candidates = [
        Path(sys.executable).resolve().parent / "prisma",
        Path(__file__).resolve().parents[1] / "venv" / "bin" / "prisma",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    raise FileNotFoundError(
        "Unable to locate the Prisma CLI. Expected it in PATH or venv/bin/prisma."
    )


def _push_prisma_schema(db_url: str):
    """Applique le schéma Prisma dans la base de tests."""
    subprocess.run(
        [_resolve_prisma_cli(), "db", "push", "--skip-generate"],
        env={**os.environ, "DATABASE_URL": db_url},
        check=True,
    )


@pytest.fixture(scope="session")
def postgres_test_database():
    with PostgresContainer("postgres:18.1-alpine3.23") as postgres:
        db_url = _to_prisma_database_url(postgres.get_connection_url())
        os.environ["DATABASE_URL"] = db_url
        _push_prisma_schema(db_url)
        yield db_url

# NE PAS RÉUTILISER. UTILISER prisma_tx SI BESOIN DE PRISMA
@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def prisma_client(postgres_test_database: str):
    prisma = Prisma()
    await prisma.connect()
    yield prisma
    await prisma.disconnect()

@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def seed_db(prisma_client: Prisma):
    """Purge et peuple la BDD une seule fois au début de la session de tests."""
    # Purge (ordre respectant les FK)
    await prisma_client.currency.delete_many()
    await prisma_client.wallet.delete_many()
    await prisma_client.log.delete_many()
    await prisma_client.claim.delete_many()

    yield

    # Nettoyage après tous les tests
    await prisma_client.currency.delete_many()
    await prisma_client.wallet.delete_many()
    await prisma_client.log.delete_many()
    await prisma_client.claim.delete_many()

@pytest_asyncio.fixture
async def prisma_tx(prisma_client: Prisma):
    tx =  prisma_client.tx()
    transaction = await tx.start()
    try:
        yield transaction

    finally:
        await tx.rollback()

@pytest.fixture
def log():
    log = Logger()
    yield log
