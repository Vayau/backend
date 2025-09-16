from supabase import Client , create_client 
import os
from dotenv import load_dotenv 

load_dotenv()

supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
