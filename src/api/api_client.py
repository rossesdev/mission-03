import httpx
import time


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
                    return response.json()

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


def get_carts(limit=10, skip=0):
    params = {"limit": limit, "skip": skip}
    return _fetch_page("carts", params=params)

def get_users(limit=10, skip=0):
    params = {
        "limit": limit,
        "skip": skip,
        "select": "id,firstName,lastName,address,company",
    }
    return _fetch_page("users", params=params)