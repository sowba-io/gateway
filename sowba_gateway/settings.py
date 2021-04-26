from typing import List

from pydantic import BaseModel, BaseSettings


class Downstream(BaseModel):
    base_url: str
    openapi_url: str


class Settings(BaseSettings):
    services: List[Downstream]
    port: int = 7000
    host: str = "0.0.0.0"
