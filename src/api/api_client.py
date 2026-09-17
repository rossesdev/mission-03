import json
import os
import httpx
import time
from pathlib import Path
import hashlib

MAX_RETRIES = 3
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

BASE_URL = os.getenv(
    "DUMMYJSON_BASE_URL",
    "https://dummyjson.com",
)

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

def _validate_page(http_response, resource, *, skip, limit, expected_total):
    required_fields = {resource, 'total', 'skip', 'limit'}

    content_type = http_response.headers.get("Content-Type", "").lower()
    if "application/json" not in content_type:
        raise ValueError(f"Expected application/json, received {content_type or 'missing'}")

    try:
        payload = http_response.json()
    except json.JSONDecodeError as error:
        raise ValueError("Response does not contain valid JSON") from error

    if not isinstance(payload, dict):
        raise ValueError("Response JSON must be an object")

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

    expected_count = min(limit, total - skip)

    if payload["limit"] != expected_count:
        raise ValueError(
            f"Unexpected limit: expected={expected_count}, returned={payload['limit']}"
        )


    for item in items:
        if not isinstance(item, dict) or "id" not in item:
            raise ValueError(f"Invalid item in '{resource}'")

    return items, total

def _save_raw_page(resource, params, run_id,* , response_body):
    folder = "output/raw"
    file_path = Path(folder) / run_id / f"{resource}_skip_{params['skip']}.json"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open('xb') as raw_file:
        raw_file.write(response_body)
    return file_path

def _calculate_hash(response_in_bytes):
    return hashlib.sha256(response_in_bytes).hexdigest()


def _get_all(endpoint, resource, pages, run_id,  *, extra_params=None ):
    skip, limit, total = 0, 10, None
    all_items = []
    seen_ids = set()
    
    while total is None or len(all_items) < total:
        params = {"limit": limit, "skip": skip, **(extra_params or {})}
        http_response = _fetch_page(endpoint, params=params)
        file_path = _save_raw_page(resource, params, run_id, response_body=http_response.content)

        items, total = _validate_page(http_response, resource, skip=skip, limit=limit, expected_total=total)
    
        hash_value = _calculate_hash(http_response.content)
        pages.append({
            "file_name": file_path.name,
            "endpoint": endpoint, 
            "status_code": http_response.status_code,
            "params": params,
            "received_count": len(items),
            "total": total,
            "sha256": hash_value,
        })

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

def get_all_carts(run_id, pages):
    _get_all("carts", "carts", pages, run_id=run_id)
  

def get_all_users(run_id, pages):
    _get_all("users", "users", pages, run_id=run_id, extra_params={"select": "id,firstName,lastName,address,company"})

def create_manifest(run_id, users_pages, carts_pages, started_at, finished_at, status):
    folder = "output/raw"
    file_path = Path(folder) / run_id / "manifest.json"
    file_path.parent.mkdir(parents=True, exist_ok=True)

    manifest = {
        "started_at": started_at,
        "finished_at": finished_at,
        "status": status,
        "run_id": run_id,
        "users_pages": users_pages,
        "carts_pages": carts_pages,
    }

    file_path.write_text(json.dumps(manifest, indent=4))


    
