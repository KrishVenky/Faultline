import httpx

from faultline.config import GRAPH_API_KEY, GRAPH_GATEWAY_URL


class GraphQLError(RuntimeError):
    pass


def query_subgraph(subgraph_id: str, query: str, variables: dict | None = None) -> dict:
    url = GRAPH_GATEWAY_URL.format(subgraph_id=subgraph_id)
    response = httpx.post(
        url,
        json={"query": query, "variables": variables or {}},
        headers={"Authorization": f"Bearer {GRAPH_API_KEY}"},
        timeout=30.0,
    )
    response.raise_for_status()
    body = response.json()
    if "errors" in body:
        raise GraphQLError(f"{subgraph_id}: {body['errors']}")
    return body["data"]


def current_block(subgraph_id: str) -> int:
    data = query_subgraph(subgraph_id, "{ _meta { block { number } } }")
    return data["_meta"]["block"]["number"]
