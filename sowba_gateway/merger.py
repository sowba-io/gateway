import asyncio
import os
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

import httpx

from .routes import MatchedRoute
from .types import OpenAPISpecType, ServiceType
from .utils import get_nested_value, read_json_resp


def get_json_schema_dm(spec: OpenAPISpecType, ref: str) -> Optional[Dict[str, Any]]:
    parts = ref.replace("#/", "").split("/")
    loc = spec
    for part in parts:
        try:
            loc = loc[part]  # type: ignore
        except KeyError:
            return None
    return loc  # type: ignore


def find_resolver_paths(
    services: List[ServiceType], result: Dict[str, Any], ref: Optional[str]
) -> List[MatchedRoute]:
    if ref is None:
        return []

    results = []
    for service in services:
        for route_path, path_data in service.spec["paths"].items():
            if "get" not in path_data.keys():
                continue
            aref = get_nested_value(
                path_data,
                ("get", "responses", "200", "content", "application/json", "schema", "$ref"),
            )
            if aref != ref:
                continue
            model = get_json_schema_dm(service.spec, ref)
            if model is None:
                continue

            # check if we have to fill data this endpoint provides
            if len(set(model.get("properties", {}).keys()) - set(result.keys())) > 0:
                real_path = []
                for path_part in route_path.split("/"):
                    if len(path_part) > 1 and path_part[0] == "{":
                        # need to replace variable with part of data
                        path_part = result[path_part.strip("{}")]
                    real_path.append(path_part)
                results.append(
                    MatchedRoute(
                        service=service,
                        path_data=path_data["get"],  # type: ignore
                        path="/".join(real_path),
                        route_path=route_path,
                        ref=aref,
                    )
                )
    return results


class RequestMerger:
    def __init__(self, session: httpx.AsyncClient, services: List[ServiceType]):
        self.services = services
        self.session = session

    async def merge(
        self,
        matches: List[MatchedRoute],
        result: Dict[str, Any],
        ref: Optional[str],
    ) -> None:
        for match in matches:
            url = os.path.join(match.service.downstream.base_url, match.path.lstrip("/"))
            resp = await self.session.get(url)
            result.update(await read_json_resp(resp))

        if ref is None:
            # can't do anything more
            return

        # look for referenced refs to check resolution for
        for service in self.services:
            model = get_json_schema_dm(service.spec, ref)
            if model is None:
                continue

            for name, prop in model.get("properties", {}).items():
                if name not in result:
                    continue

                if prop.get("type") == "array" and "$ref" in (prop.get("items") or {}):
                    reqs = []
                    sub_ref = get_nested_value(prop, ("items", "$ref"))
                    for sub_result in result[name]:
                        reqs.append(
                            self.merge(
                                find_resolver_paths(self.services, sub_result, sub_ref),
                                sub_result,
                                sub_ref,
                            )
                        )
                    await asyncio.wait(reqs)

                if "$ref" in prop:
                    await self.merge(
                        find_resolver_paths(self.services, result[name], prop["$ref"]),
                        result[name],
                        prop["$ref"],
                    )
