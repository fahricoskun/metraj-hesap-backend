import ezdxf

def create_test_dxf():
    # Yeni bir DXF dökümanı oluştur (AutoCAD 2010 formatı)
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    # Test Katmanlarımızı (Layers) Tanımlayalım
    doc.layers.add('KOLON_C30', color=1)       # Kırmızı
    doc.layers.add('PERDE_C30', color=3)       # Yeşil
    doc.layers.add('DUVAR_GAZBETON', color=4)  # Cam Göbeği

    # --- 1. KOLONLAR (4 Köşeye 1x1 metrelik tam kapalı poligonlar) -> Toplam Alan: 4 m² ---
    # Canvas bounding box test etmek için (0,0) ile (10,10) sınırlarına koyuyoruz
    msp.add_lwpolyline([(0, 0), (1, 0), (1, 1), (0, 1)], close=True, dxfattribs={'layer': 'KOLON_C30'})
    msp.add_lwpolyline([(9, 0), (10, 0), (10, 1), (9, 1)], close=True, dxfattribs={'layer': 'KOLON_C30'})
    msp.add_lwpolyline([(0, 9), (1, 9), (1, 10), (0, 10)], close=True, dxfattribs={'layer': 'KOLON_C30'})
    msp.add_lwpolyline([(9, 9), (10, 9), (10, 10), (9, 10)], close=True, dxfattribs={'layer': 'KOLON_C30'})

    # --- 2. BETONARME PERDE (Merkeze 4x1 metrelik bir perde) -> Toplam Alan: 4 m² ---
    msp.add_lwpolyline([(3, 4.5), (7, 4.5), (7, 5.5), (3, 5.5)], close=True, dxfattribs={'layer': 'PERDE_C30'})

    # --- 3. DUVARLAR (Kolonları birleştiren temsili kapalı alanlar) ---
    # Üst Duvar (7x0.5 metre) -> Alan: 3.5 m²
    msp.add_lwpolyline([(1, 9.25), (9, 9.25), (9, 9.75), (1, 9.75)], close=True, dxfattribs={'layer': 'DUVAR_GAZBETON'})
    
    # Dosyayı Kaydet
    filename = "metraj_test_sahnesi.dxf"
    doc.saveas(filename)
    print(f"✅ {filename} başarıyla üretildi!")
    print("Sınırlar (Bounding Box): X(0 -> 10), Y(0 -> 10)")
    print("Beklenen Kolon Alanı: Tam 4.00 m²")
    print("Beklenen Perde Alanı: Tam 4.00 m²")

if __name__ == "__main__":
    create_test_dxf()