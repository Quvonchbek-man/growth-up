from aiogram import Router

from bot.handlers import dev, nudge, start, tasks


def get_router() -> Router:
    """Tartib muhim: `fallback` oxirida bo'lishi kerak."""
    router = Router(name="root")
    router.include_router(start.router)
    router.include_router(tasks.router)
    router.include_router(nudge.router)
    router.include_router(dev.router)
    return router


__all__ = ["get_router"]
