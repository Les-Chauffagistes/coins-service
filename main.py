import signal

from init import routes, app, log
from src.settings import settings
from aiohttp import web
from asyncio import Event, get_running_loop, new_event_loop, set_event_loop


async def main():
    log.info("Démarrage du serveur...")

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", settings.server_port)
    await site.start()
    log.info(f"Serveur interne en ligne sur localhost:{settings.server_port}")

    # `runner.cleanup()` est ce qui déclenche les handlers `app.on_cleanup`
    # (close_prisma, shutdown_tracing) — sans handler de signal explicite, un
    # SIGTERM (envoyé par Swarm à chaque redéploiement) tue le process sans
    # jamais les exécuter : la connexion Prisma et les spans bufferisés ne se
    # ferment/flushent proprement nulle part.
    stop = Event()
    loop = get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    await stop.wait()

    log.info("Arrêt en cours...")
    await runner.cleanup()


if __name__ == "__main__":
    from src import v1, health

    from src.v1.app import routes as v1_routes
    app.add_routes(routes)
    app.add_routes(v1_routes)

    loop = new_event_loop()
    set_event_loop(loop)
    loop.run_until_complete(main())
    log.info("Bye")
