import src.api.api_client as api_client
from datetime import datetime, UTC
from pathlib import Path
 
def run_pipeline():
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    cart_pages = []
    user_pages = []
    status = "running"
    finished_at = None
    started_at = datetime.now(UTC).isoformat()

    folder = "output/raw"
    file_path = Path(folder) / run_id
    file_path.mkdir(parents=True, exist_ok=False)

    api_client.create_manifest(run_id, user_pages, cart_pages, started_at, finished_at, status)

    try:
        api_client.get_all_carts(run_id, cart_pages)
        api_client.get_all_users(run_id, user_pages)
    except Exception:
        status = "failed"
        finished_at = datetime.now(UTC).isoformat()
        api_client.create_manifest(run_id, user_pages, cart_pages, started_at, finished_at, status)
        raise
    
    status = "succeeded"
    finished_at = datetime.now(UTC).isoformat()

    api_client.create_manifest(run_id, user_pages, cart_pages, started_at, finished_at, status)

if __name__ == "__main__":
    run_pipeline()