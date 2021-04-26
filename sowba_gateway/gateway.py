import os
from typing import (
    Any,
    Dict,
    List,
    cast,
)

import httpx
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.types import Scope

from sowba_gateway.settings import Settings

from .merger import RequestMerger
from .routes import RouteMatcher
from .types import OpenAPISpecType, ServiceType
from .utils import read_json_resp


class GatewayApp(FastAPI):
    session: httpx.AsyncClient
    services: List[ServiceType]
    matcher: RouteMatcher

    def __init__(self, settings: Settings):
        super().__init__(on_startup=[self.startup], on_shutdown=[self.shutdown])
        self.session = httpx.AsyncClient()
        self.settings = settings
        self.services = []
        self.matcher = RouteMatcher(self.services)
        self.merger = RequestMerger(self.session, self.services)

    async def shutdown(self) -> None:
        await self.session.aclose()

    async def startup(self) -> None:
        # load downstreams
        for downstream in self.settings.services:
            resp = await self.session.get(downstream.openapi_url)
            spec = cast(OpenAPISpecType, await read_json_resp(resp))
            self.services.append(ServiceType(downstream=downstream, spec=spec))

    async def proxy_request(self, scope: Scope, receive, send, url: str):
        request = Request(scope, receive, send)
        func = getattr(self.session, request.method)
        downstream_resp = await func(url, data=request.stream())
        req_resp = StreamingResponse(
            downstream_resp.aiter_bytes(),
            status_code=downstream_resp.status_code,
            headers=downstream_resp.headers,
        )
        await req_resp(scope, receive, send)

    async def __call__(self, scope: Scope, receive, send) -> None:
        scope["app"] = self

        assert scope["type"] in ("http", "websocket", "lifespan")

        if scope["type"] == "lifespan":
            await self.router.lifespan(scope, receive, send)
            return

        method = scope["method"].lower()
        matches = self.matcher.find_routes(method=method, path=scope["path"])

        if len(matches) == 0:
            response = JSONResponse({"reason": "noRouteFound"}, status_code=404)
            await response(scope, receive, send)
        elif method != "get" or len(matches) == 1:
            if len(matches) > 1:
                response = JSONResponse(
                    {"reason": "ambiguousRoute", "details": "Multiple routes matched request"},
                    status_code=500,
                )
                await response(scope, receive, send)
            else:
                # proxy these requests
                url = os.path.join(
                    matches[0].service.downstream.base_url, scope["path"].lstrip("/")
                )
                await self.proxy_request(scope, receive, send, url)
        else:
            # validate all refs match for mergable routes
            refs = [m.ref for m in matches]
            if refs.count(refs[0]) != len(refs):
                response = JSONResponse(
                    {
                        "reason": "ambiguousRoute",
                        "details": "Conflicting downstream services",
                        "refs": [
                            {
                                "service": match.service.spec.get("info"),
                                "ref": match.ref,
                            }
                            for match in matches
                        ],
                    },
                    status_code=500,
                )
                await response(scope, receive, send)
            else:
                result: Dict[str, Any] = {}
                await self.merger.merge(matches, result, refs[0])
                response = JSONResponse(result, status_code=200)
                await response(scope, receive, send)
