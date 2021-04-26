from dataclasses import dataclass
from typing import Dict, Optional, TypedDict

from .settings import Downstream


class OpenAPIPathType(TypedDict):
    ...


class OpenAPIInfo(TypedDict):
    title: Optional[str]
    description: Optional[str]


class OpenAPISpecType(TypedDict):
    info: OpenAPIInfo
    paths: Dict[str, Dict[str, OpenAPIPathType]]


@dataclass
class ServiceType:
    downstream: Downstream
    spec: OpenAPISpecType
