import os
from supabase import create_client, Client
from dotenv import load_dotenv

# load_dotenv() mevcut dizindeki veya üst dizindeki .env dosyasını bulup yükler.
load_dotenv()

# Çevresel değişkenlerden Supabase kimlik bilgilerini alıyoruz.
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

class SupabaseHelper:
    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            print("UYARI: SUPABASE_URL veya SUPABASE_ANON_KEY bulunamadı. Lütfen .env dosyasını kontrol edin.")
            self.client = None
        else:
            # Supabase istemcisini oluşturuyoruz
            self.client: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
            
    def get_client(self) -> Client:
        """Supabase client nesnesini döndürür."""
        return self.client
    
    # İhtiyaca göre örnek CRUD metotları
    def insert_record(self, table_name: str, data: dict):
        if not self.client:
            return {"error": "Supabase client başlatılamadı."}
        try:
            response = self.client.table(table_name).insert(data).execute()
            return response
        except Exception as e:
            return {"error": str(e)}

    def get_records(self, table_name: str):
        if not self.client:
            return {"error": "Supabase client başlatılamadı."}
        try:
            response = self.client.table(table_name).select("*").execute()
            return response
        except Exception as e:
            return {"error": str(e)}

# Proje genelinde import edilip kullanılabilecek hazır bir instance
supabase_db = SupabaseHelper()
