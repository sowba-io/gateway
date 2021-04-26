from dataclasses import dataclass
from typing import (
    Any,
    Dict,
    List,
    Optional,
    cast,
)

from .types import ServiceType
from .utils import get_nested_value


@dataclass
class MatchedRoute:
    service: ServiceType
    path: str
    route_path: str
    path_data: Dict[str, Any]
    ref: Optional[str]


class RouteMatcher:
    def __init__(self, services: List[ServiceType]):
        self.services = services

    def find_routes(self, *, method: str, path: str) -> List[MatchedRoute]:
        path_parts = path.split("/")
        matches = []
        for service in self.services:
            for route_path, path_data in service.spec.get("paths", {}).items():
                if method not in path_data.keys():
                    continue

                if len(path_parts) != len(route_path.split("/")):
                    continue

                for idx, path_part in enumerate(route_path.split("/")):
                    if idx >= len(path_parts):
                        break
                    if path_parts[idx] != path_part:
                        if path_part[0] == "{":
                            continue
                        else:
                            break
                else:
                    matches.append(
                        MatchedRoute(
                            service=service,
                            path_data=cast(Dict[str, Any], path_data[method]),
                            route_path=route_path,
                            path=path,
                            ref=get_nested_value(
                                path_data[method],  # type: ignore
                                (
                                    "responses",
                                    "200",
                                    "content",
                                    "application/json",
                                    "schema",
                                    "$ref",
                                ),
                            ),
                        )
                    )
        return matches
