import httpx
import time
import json
from pathlib import Path
from datetime import datetime, UTC

BASE_URL = "https://dummyjson.com"
MAX_RETRIES = 3
RETRYABLE_STATUS_CODES = {429, *range(500, 600)}

# manage pagination in blucle until the skip = total


def _fetch_page(endpoint, params=None):
    with httpx.Client(
        base_url=BASE_URL,
        headers={"User-Agent": "mission-03/0.1"},
        timeout=10.0,
    ) as client:
        for retry in range(MAX_RETRIES + 1):
            try:
                response = client.get(f"/{endpoint}", params=params)

                if response.status_code not in RETRYABLE_STATUS_CODES:
                    response.raise_for_status()
                    return response

                if retry == MAX_RETRIES:
                    response.raise_for_status()

                retry_after = response.headers.get("Retry-After")
                delay = (
                    float(retry_after)
                    if retry_after and retry_after.isdigit()
                    else 2**retry
                )
            
            except httpx.TransportError:
                if retry == MAX_RETRIES:
                    raise
                delay = 2**retry
            time.sleep(delay)

def _validate_page(payload, resource, *, skip, limit, expected_total):
    required_fields = {resource, 'total', 'skip', 'limit'}
    missing_fields = required_fields - payload.keys()

    if missing_fields:
        raise ValueError(
            f"Missing required fields in {resource} response: {sorted(missing_fields)}"
        )

    items = payload[resource]

    if not isinstance(items, list):
        raise ValueError(f"{resource.capitalize()} response '{resource}' field is not a list")

    if not items and expected_total != 0:
        raise ValueError(f"{resource.capitalize()} response '{resource}' field is empty")

    if len(items) > limit:
        raise ValueError(
            f"Received {len(items)} items, but the requested limit was {limit}"
        )

    total = payload["total"]
    if expected_total is not None and total != expected_total:
        raise ValueError(
            f"Unexpected total value in {resource} response: expected_total={expected_total}, total={total}"
        )

    if payload["skip"] != skip:
        raise ValueError(
            f"Unexpected skip: requested={skip}, returned={payload['skip']}"
        )
    
    for item in items:
        if not isinstance(item, dict) or "id" not in item:
            raise ValueError(f"Invalid item in '{resource}'")

    return items, total

def _save_raw_page(payload, resource, params, run_id, status_code):
    folder = "output/raw"
    file_path = Path(folder) / run_id / f"{resource}_skip_{params['skip']}.json"
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w") as f:
        json.dump(
            {
                "body": payload,
                "status": status_code,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "resource": resource,
                "params": params,
            },
            f,
            indent=4,
        )


def _get_all(endpoint, resource, *, extra_params=None):
    skip, limit, total = 0, 10, None
    all_items = []
    seen_ids = set()
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    while total is None or len(all_items) < total:
        params = {"limit": limit, "skip": skip, **(extra_params or {})}

        http_response = _fetch_page(endpoint, params=params)
        payload = http_response.json()

        _save_raw_page(payload, resource, params, run_id, status_code=http_response.status_code)

        items, total = _validate_page(payload, resource, skip=skip, limit=limit, expected_total=total)

        duplicate_ids = seen_ids & {item["id"] for item in items}

        if duplicate_ids:
            raise ValueError(f"Duplicate {resource[:-1]} IDs found: {sorted(duplicate_ids)}")
        
        all_items.extend(items)
        seen_ids.update(item["id"] for item in items)
        skip += limit

    if len(all_items) != total:
        raise ValueError(
            f"Mismatch between fetched {resource} and total: fetched={len(all_items)}, total={total}"
        )

    return all_items
          

def get_all_carts():
    return _get_all("carts", "carts")

def get_all_users():
    return _get_all("users", "users", extra_params={"select": "id,firstName,lastName,address,company"})


get_all_carts()