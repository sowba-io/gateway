from typing import (
    Any,
    Dict,
    Optional,
    Tuple,
)

import httpx
import orjson


def get_nested_value(dic: Dict[str, Any], props: Tuple[str, ...]) -> Optional[Any]:
    for prop in props:
        if prop not in dic:
            return None
        dic = dic[prop]

    return dic


async def read_json_resp(resp: httpx.Response) -> Dict[str, Any]:
    data = b""
    async for chunk in resp.aiter_bytes():
        data += chunk
    return orjson.loads(data)
