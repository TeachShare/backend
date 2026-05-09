import os
from supabase import create_client, Client

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")

if not url or not key:
    # During build or initial setup, these might be missing
    supabase: Client = None
else:
    supabase: Client = create_client(url, key)
