import os
import httpx


class SupabaseStorageClient:
    def __init__(
        self,
        supabase_url: str,
        service_role_key: str,
        public_base_url: str | None = None,
    ):
        self.supabase_url = supabase_url.rstrip("/")
        self.service_role_key = service_role_key
        self.public_base_url = (public_base_url or f"{self.supabase_url}/storage/v1/object/public").rstrip("/")

    def _build_public_url(self, bucket: str, dest_path: str) -> str:
        clean = dest_path.lstrip("/")
        return f"{self.public_base_url}/{bucket}/{clean}"

    def upload_file(self, bucket: str, src_path: str, dest_path: str) -> str:
        url = f"{self.supabase_url}/storage/v1/object/{bucket}/{dest_path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/octet-stream",
            "x-upsert": "true",
        }
        with open(src_path, "rb") as f:
            resp = httpx.put(url, content=f.read(), headers=headers, timeout=60)
        if resp.status_code >= 300:
            raise RuntimeError(f"Supabase upload failed ({resp.status_code}): {resp.text}")
        return self._build_public_url(bucket, dest_path)
