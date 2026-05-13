import ezdxf
from typing import List, Dict, Union
import math
import subprocess
import os
import tempfile
import shutil
from supabase_client import supabase_db

# Common installation paths for ODA File Converter on Windows
ODA_PATHS = [
    r"C:\Program Files\ODA\ODAFileConverter 26.12.0\ODAFileConverter.exe",
    r"C:\Program Files\ODA\ODAFileConverter 25.12.0\ODAFileConverter.exe",
    r"C:\Program Files\ODA\ODAFileConverter_25.12.0\ODAFileConverter.exe",
    r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe",
]

def find_oda_converter() -> str:
    """Checks for ODA File Converter executable dynamically."""
    for path in ODA_PATHS:
        if os.path.exists(path):
            return path
    
    base_oda = r"C:\Program Files\ODA"
    if os.path.exists(base_oda):
        try:
            items = os.listdir(base_oda)
            for item in items:
                possible_path = os.path.join(base_oda, item, "ODAFileConverter.exe")
                if os.path.isfile(possible_path):
                    return possible_path
        except Exception:
            pass

    path_env = shutil.which("ODAFileConverter.exe")
    if path_env:
        return path_env
        
    return None

def convert_dwg_to_dxf(dwg_content: bytes) -> bytes:
    converter_path = find_oda_converter()
    if not converter_path:
        raise EnvironmentError(
            "DWG→DXF dönüşümü için ODA File Converter gereklidir. "
            "Sunucuda kurulu değil — lütfen dosyayı .dxf olarak dışa aktarıp tekrar yükleyiniz."
        )

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = os.path.join(temp_dir, "input")
            output_dir = os.path.join(temp_dir, "output")
            os.makedirs(input_dir)
            os.makedirs(output_dir)

            input_path = os.path.join(input_dir, "source.dwg")
            with open(input_path, "wb") as f:
                f.write(dwg_content)

            cmd = [
                converter_path,
                input_dir,
                output_dir,
                "ACAD2018",
                "DXF",
                "0",
                "0"
            ]

            result = subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
            )
            output_file = os.path.join(output_dir, "source.dxf")

            if os.path.exists(output_file):
                with open(output_file, "rb") as f:
                    return f.read()
            else:
                raise RuntimeError(
                    f"ODA dönüşümü tamamlandı fakat çıktı dosyası bulunamadı. "
                    f"Stderr: {result.stderr.decode(errors='replace')[:200]}"
                )

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ODA dönüşüm süreci başarısız: {e.stderr.decode(errors='replace')[:200]}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("DWG dönüşümü zaman aşımına uğradı (60 s). Dosya çok büyük olabilir.")

def extract_layers(file_content: bytes, is_dwg: bool = False) -> List[str]:
    temp_dxf_path = None
    try:
        content_to_read = file_content
        if is_dwg:
            content_to_read = convert_dwg_to_dxf(file_content)

        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
            tmp.write(content_to_read)
            temp_dxf_path = tmp.name
            
        doc = ezdxf.readfile(temp_dxf_path)
        layers = [layer.dxf.name for layer in doc.layers]
        return sorted(layers)

    except Exception as e:
        if "ODA File Converter" in str(e):
            raise e
        print(f"Error reading CAD: {e}")
        return []
    finally:
        if temp_dxf_path and os.path.exists(temp_dxf_path):
            try:
                os.unlink(temp_dxf_path)
            except:
                pass

def calculate_layer_area(file_content: bytes, layer_name: str, is_dwg: bool = False) -> dict:
    temp_dxf_path = None
    try:
        content_to_read = file_content
        if is_dwg:
            content_to_read = convert_dwg_to_dxf(file_content)

        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
            tmp.write(content_to_read)
            temp_dxf_path = tmp.name

        doc = ezdxf.readfile(temp_dxf_path)
        msp = doc.modelspace()
        
        total_area = 0.0
        target_polygons = []
        all_lines = []
        min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')

        def update_bounds(x, y):
            nonlocal min_x, min_y, max_x, max_y
            if x < min_x: min_x = x
            if x > max_x: max_x = x
            if y < min_y: min_y = y
            if y > max_y: max_y = y

        line_count = 0
        for entity in msp:
            if entity.dxftype() == 'LINE' and line_count < 10000:
                start = entity.dxf.start
                end = entity.dxf.end
                all_lines.append({'start': {'x': start.x, 'y': start.y}, 'end': {'x': end.x, 'y': end.y}})
                update_bounds(start.x, start.y)
                update_bounds(end.x, end.y)
                line_count += 1
            elif entity.dxftype() == 'LWPOLYLINE' and line_count < 10000:
                pts = list(entity.get_points())
                for i in range(len(pts) - 1):
                    all_lines.append({'start': {'x': pts[i][0], 'y': pts[i][1]}, 'end': {'x': pts[i+1][0], 'y': pts[i+1][1]}})
                    update_bounds(pts[i][0], pts[i][1])
                    line_count += 1
                if entity.is_closed and len(pts) > 0:
                    all_lines.append({'start': {'x': pts[-1][0], 'y': pts[-1][1]}, 'end': {'x': pts[0][0], 'y': pts[0][1]}})
                    update_bounds(pts[-1][0], pts[-1][1])

        try:
            polylines = msp.query(f'LWPOLYLINE[layer=="{layer_name}"]')
        except Exception:
            polylines = []
        
        for pl in polylines:
            if pl.is_closed:
                points = list(pl.get_points())
                poly_area = _calculate_polygon_area(points)
                total_area += poly_area
                
                coords = [{'x': p[0], 'y': p[1]} for p in points]
                target_polygons.append(coords)
                
        if min_x == float('inf'):
            min_x, min_y, max_x, max_y = 0, 0, 100, 100
                
        return {
            "total_area": total_area,
            "target_polygons": target_polygons,
            "all_lines": all_lines,
            "bounding_box": {"min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y}
        }
    except Exception as e:
        if "ODA File Converter" in str(e):
            raise e
        print(f"Error calculating area: {e}")
        return {
            "total_area": 0.0,
            "target_polygons": [],
            "all_lines": [],
            "bounding_box": {"min_x": 0, "min_y": 0, "max_x": 100, "max_y": 100}
        }
    finally:
        if temp_dxf_path and os.path.exists(temp_dxf_path):
            try:
                os.unlink(temp_dxf_path)
            except:
                pass

def _calculate_polygon_area(points: List[tuple]) -> float:
    area = 0.0
    if len(points) < 3:
        return 0.0
        
    for i in range(len(points)):
        j = (i + 1) % len(points)
        area += points[i][0] * points[j][1]
        area -= points[j][0] * points[i][1]
        
    return abs(area) / 2.0

def calculate_metrics_and_cost(file_content: bytes, layer_name: str, height: float, unit: str = "m", is_dwg: bool = False) -> dict:
    layer_data = calculate_layer_area(file_content, layer_name, is_dwg)
    raw_area = layer_data["total_area"]
    
    if unit == "cm":
        area_m2 = raw_area / 10000.0 
    else:
        area_m2 = raw_area
    
    volume_m3 = area_m2 * height
    
    DENSITY = 2.5 # t/m3
    weight_ton = volume_m3 * DENSITY
    
    FIRE_BETON = 1.03 
    FIRE_DEMIR = 1.05 
    
    volume_m3_with_fire = volume_m3 * FIRE_BETON
    weight_ton_with_fire = weight_ton * FIRE_DEMIR
    
    # Dinamik Fiyatları Supabase'den Çekme (Genişletilmiş Kapsam)
    prices = {
        "beton": 2800.0,
        "demir": 24500.0,
        "hafriyat": 350.0,
        "seramik": 650.0,
        "boya": 180.0
    }
    
    try:
        client = supabase_db.get_client()
        if client:
            response = client.table('birim_fiyatlar').select('*').execute()
            if response.data:
                for row in response.data:
                    name = str(row.get('malzeme', '')).lower()
                    price = float(row.get('fiyat', row.get('fiyat_tl', 0.0)))
                    
                    if price > 0:
                        if 'beton' in name: prices["beton"] = price
                        elif 'demir' in name: prices["demir"] = price
                        elif 'hafriyat' in name or 'kazı' in name: prices["hafriyat"] = price
                        elif 'seramik' in name or 'fayans' in name: prices["seramik"] = price
                        elif 'boya' in name or 'sıva' in name: prices["boya"] = price
    except Exception as e:
        print(f"Supabase'den fiyat çekerken hata olustu: {e}")

    # Kaba İnşaat İçin Varsayılan Toplam Maliyet Formülü
    estimated_cost_tl = (volume_m3_with_fire * prices["beton"]) + (weight_ton_with_fire * prices["demir"])

    return {
        # Birincil alan değerleri — frontend otomatik doldurma için her ikisi de sağlanır
        "area_m2": round(area_m2, 2),
        "total_area": round(area_m2, 2),
        "volume_m3": round(volume_m3, 2),
        "weight_ton": round(weight_ton, 2),
        "raw_area": raw_area,
        "estimated_cost_tl": round(estimated_cost_tl, 2),
        "fire_rates": {
            "beton": "3%",
            "demir": "5%"
        },
        "prices_used": prices,
        "cad_geometry": {
            "target_polygons": layer_data["target_polygons"],
            "all_lines": layer_data["all_lines"],
            "bounding_box": layer_data["bounding_box"]
        }
    }