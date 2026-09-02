from os import getenv
from src.database.prisma import close_prisma, init_prisma
from src.middlewares.logger import error_handler
from src.middlewares.cors import cors_middleware
from chauff_cmn.logging import configure
from chauff_cmn.logging.aiohttp import request_logging_middleware
from chauff_cmn.tracing import setup_tracing, shutdown_tracing
from aiohttp.web import Application, RouteTableDef

configure(service="coins-service", level=getenv("LOG_LEVEL", "DEBUG"))
setup_tracing(service="coins-service")

app = Application(
    middlewares=(cors_middleware, request_logging_middleware, error_handler)
)


async def _shutdown_tracing(app: Application) -> None:
    shutdown_tracing()


app.on_startup.append(init_prisma) # enregistre prisma dans app["prisma"]
app.on_cleanup.append(close_prisma)
app.on_cleanup.append(_shutdown_tracing)
routes = RouteTableDef()