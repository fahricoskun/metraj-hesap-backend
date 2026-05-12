import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_all_material_prices():
    """Tüm güncel malzeme fiyatlarını Supabase'den çeker."""
    try:
        response = supabase.table("materials").select("*").execute()
        return response.data
    except Exception as e:
        print(f"Supabase Bağlantı Hatası: {e}")
        # Bağlantı koparsa sistemin çökmemesi için Fallback (Yedek) veriler
        return [
            {"poz_no": "15.120.1005", "current_price": 2800.00, "unit": "m³"},
            {"poz_no": "15.080.1002", "current_price": 24500.00, "unit": "Ton"}
        ]

def get_price_by_poz(poz_no: str) -> float:
    """Belirli bir poz numarasına ait güncel fiyatı döndürür."""
    try:
        response = supabase.table("materials").select("current_price").eq("poz_no", poz_no).execute()
        if response.data:
            return float(response.data[0]["current_price"])
    except Exception as e:
        print(f"Fiyat çekilemedi ({poz_no}): {e}")
    return 0.0