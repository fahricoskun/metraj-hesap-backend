from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import uvicorn
import cad_service
import io
import json
import os
from supabase_client import supabase_db

app = FastAPI(title="MetrajPro Enterprise Backend API")

# Enable CORS for frontend (Vercel & Dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production'da buraya Vercel domaini eklenmeli
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalysisRequest(BaseModel):
    layer_name: str
    height: float  # meters

@app.get("/")
def read_root():
    return {"message": "MetrajPro Enterprise CAD & Hakediş Backend is running"}

@app.get("/api/prices")
async def get_all_prices():
    """
    Frontend Context'ini beslemek için tüm güncel malzeme fiyatlarını döner.
    Supabase bağlantısı başarısız olursa güvenli fallback değerleri gönderir.
    """
    default_prices = {
        "Beton": 2800.00,
        "Demir": 24500.00,
        "Hafriyat": 350.00,
        "Seramik": 650.00,
        "Boya": 180.00
    }
    
    try:
        client = supabase_db.get_client()
        if client:
            response = client.table('birim_fiyatlar').select('*').execute()
            if response.data:
                db_prices = {}
                for row in response.data:
                    name = str(row.get('malzeme', '')).lower()
                    price = float(row.get('fiyat', row.get('fiyat_tl', 0.0)))
                    if price > 0:
                        if 'beton' in name: db_prices["Beton"] = price
                        elif 'demir' in name: db_prices["Demir"] = price
                        elif 'hafriyat' in name or 'kazı' in name: db_prices["Hafriyat"] = price
                        elif 'seramik' in name or 'fayans' in name: db_prices["Seramik"] = price
                        elif 'boya' in name or 'sıva' in name: db_prices["Boya"] = price
                # Merge DB prices with defaults
                default_prices.update(db_prices)
    except Exception as e:
        print(f"Global price fetch error: {e}")

    return {"status": "success", "data": default_prices}

@app.post("/analyze/layers")
async def get_layers(file: UploadFile = File(...)):
    """
    Upload a DXF/DWG file and get a list of available layers.
    """
    if not file.filename.lower().endswith(('.dxf', '.dwg')):
        raise HTTPException(status_code=400, detail="Only .dxf and .dwg files are supported")
        
    content = await file.read()
    is_dwg = file.filename.lower().endswith('.dwg')
    
    try:
        layers = cad_service.extract_layers(content, is_dwg=is_dwg)
        return {"layers": layers, "detected_layers": layers}
    except EnvironmentError as e:
        return {
            "warning": str(e),
            "layers": [],
            "detected_layers": [],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze/calculate")
async def calculate_concrete(
    file: UploadFile = File(...), 
    layer_name: str = Form(...), 
    height: float = Form(...),
    unit: str = Form("m")
):
    """
    Calculate area, volume, weight, and estimated cost for a specific CAD layer.
    """
    content = await file.read()
    is_dwg = file.filename.lower().endswith('.dwg')

    try:
        result = cad_service.calculate_metrics_and_cost(content, layer_name, height, unit=unit, is_dwg=is_dwg)
        return result
    except EnvironmentError as e:
        # ODA Converter eksik — 503 döndür, frontend kullanıcıya açıklayıcı mesaj gösterir
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analyze/market")
async def get_market_analysis():
    """
    Canlı piyasa analizi, regresyon tabanlı tahminleme ve AI tabanlı alım stratejisi sunar.
    """
    file_path = os.path.join(os.path.dirname(__file__), 'market_data.json')
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            history = json.load(f)
    except Exception as e:
        history = []

    # Varsayılan Güncel Değerler
    beton_current = 2800.0
    demir_current = 24500.0
    
    try:
        client = supabase_db.get_client()
        if client:
            response = client.table('birim_fiyatlar').select('*').execute()
            if response.data:
                for row in response.data:
                    name = str(row.get('malzeme', '')).lower()
                    price = float(row.get('fiyat', row.get('fiyat_tl', 0.0)))
                    if 'beton' in name and price > 0:
                        beton_current = price
                    elif 'demir' in name and price > 0:
                        demir_current = price
    except Exception as e:
        print(f"Market fetch error: {e}")

    last_year_data = history[-4:] if len(history) >= 4 else history
    
    if last_year_data:
        avg_beton_12m = sum(d['beton'] for d in last_year_data) / len(last_year_data)
        avg_demir_12m = sum(d['demir'] for d in last_year_data) / len(last_year_data)
        max_beton_12m = max(d['beton'] for d in last_year_data)
        min_beton_12m = min(d['beton'] for d in last_year_data)
        max_demir_12m = max(d['demir'] for d in last_year_data)
        min_demir_12m = min(d['demir'] for d in last_year_data)
    else:
        avg_beton_12m = beton_current
        avg_demir_12m = demir_current
        max_beton_12m = min_beton_12m = beton_current
        max_demir_12m = min_demir_12m = demir_current

    def get_insight(current, max_val, min_val):
        if current >= max_val:
            return "son 1 yılın en yüksek seviyesinde"
        elif current <= min_val:
            return "son 1 yılın en düşük seviyesinde"
        return "son 1 yıllık dalgalanma aralığında (normal seviyede)"

    insight_beton = get_insight(beton_current, max_beton_12m, min_beton_12m)
    insight_demir = get_insight(demir_current, max_demir_12m, min_demir_12m)

    # 3-Month Regression / Forecast
    if len(last_year_data) >= 2:
        b_start = last_year_data[0]['beton']
        d_start = last_year_data[0]['demir']
        b_growth_m = ((beton_current - b_start) / b_start) / 12 if b_start > 0 else 0.01
        d_growth_m = ((demir_current - d_start) / d_start) / 12 if d_start > 0 else 0.01
    else:
        b_growth_m = 0.01
        d_growth_m = 0.01
        
    forecast_3m_beton = max(beton_current * 0.5, beton_current * ((1 + b_growth_m) ** 3))
    forecast_3m_demir = max(demir_current * 0.5, demir_current * ((1 + d_growth_m) ** 3))
    
    diff_pct_beton = ((forecast_3m_beton - beton_current) / beton_current) * 100
    diff_pct_demir = ((forecast_3m_demir - demir_current) / demir_current) * 100
    avg_diff = (diff_pct_beton + diff_pct_demir) / 2

    if avg_diff > 3:
        ai_recommendation = f"Malzemeyi şimdi almanız, 3 ay sonraya göre ortalama %{round(avg_diff, 1)} daha kârlı olabilir. Fiyatlarda yükseliş trendi öngörülüyor."
    elif avg_diff < -3:
        ai_recommendation = f"Fiyatların 3 ay içinde %{abs(round(avg_diff, 1))} düşmesi bekleniyor. Alımları ertelemek avantajlı olabilir."
    else:
        ai_recommendation = f"Önümüzdeki 3 ay için fiyatların yatay seyretmesi (%{round(avg_diff, 1)} değişim) bekleniyor. Mevcut stratejinizi koruyabilirsiniz."

    chart_data = history.copy()
    chart_data.append({
        "month": "Güncel",
        "beton": beton_current,
        "demir": demir_current
    })

    return {
        "chart_data": chart_data,
        "insights": {
            "beton": f"Mevcut fiyatlar ({beton_current} TL) {insight_beton}. 12 Aylık Ort: {round(avg_beton_12m)} TL",
            "demir": f"Mevcut fiyatlar ({demir_current} TL) {insight_demir}. 12 Aylık Ort: {round(avg_demir_12m)} TL"
        },
        "forecast": {
            "beton_3m": round(forecast_3m_beton, 2),
            "demir_3m": round(forecast_3m_demir, 2),
            "ai_recommendation": ai_recommendation
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)