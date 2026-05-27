import logfire.experimental.api_client
from fastapi import FastAPI
from loguru import logger
from starlette.middleware.cors import CORSMiddleware

from proxy.settings import CONFIG

app = FastAPI(title="Agent Proxy")


app.add_middleware(
    CORSMiddleware,
    allow_origins=CONFIG.middleware.cors.origins,
    allow_methods=CONFIG.middleware.cors.allow_methods,
    allow_headers=CONFIG.middleware.cors.allow_headers,
    allow_credentials=CONFIG.middleware.cors.allow_credentials,
)


logfire.configure(
    send_to_logfire="if-token-present",
    environment=CONFIG.logfire.environment,
    service_name=CONFIG.logfire.service_name,
    token=CONFIG.logfire.token.get_secret_value() if CONFIG.logfire.token else None,
)

logfire.instrument_fastapi(app)
logfire.instrument_system_metrics(base="basic")
logger.configure(handlers=[logfire.loguru_handler()])
