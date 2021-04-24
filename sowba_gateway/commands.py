import argparse
import logging

import dotenv
import uvicorn

from .gateway import GatewayApp
from .settings import Settings

logging.basicConfig(
    format="[%(asctime)s(%(levelname)s)%(name)s] %(message)s",
    level=logging.INFO,
)

parser = argparse.ArgumentParser(description="command runner", add_help=False)
parser.add_argument(
    "-e",
    "--env-file",
    help="Env file",
)


def get_settings() -> Settings:
    arguments, _ = parser.parse_known_args()
    if arguments.env_file is not None:
        dotenv.load_dotenv(arguments.env_file)
    return Settings()


def serve_command() -> None:
    settings = get_settings()
    uvicorn.run(
        GatewayApp(settings),
        host=settings.host,
        port=settings.port,
        log_level="info",
    )
