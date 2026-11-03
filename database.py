import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL மற்றும் SUPABASE_KEY சூழல் மாறிகள் அமைக்கப்படவில்லை.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
