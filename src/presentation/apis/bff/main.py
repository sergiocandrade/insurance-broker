from fastapi import FastAPI

from presentation.apis.bff.containers import Container
from presentation.apis.bff.exception_handler import register_exception_handlers

from .routes import auth


container = Container()
container.wire(modules=[auth])

app = FastAPI(title="Insurance Broker BFF")
register_exception_handlers(app)
app.state.container = container
app.include_router(auth.router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}