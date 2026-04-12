import math
import PyPDF2
import re
from io import BytesIO
from datetime import datetime

def process_pdf_bytes(pdf_bytes):
    """
    Liest die PDF aus und berechnet die Koordinaten AUSSCHLIESSLICH 
    über Ringzahl und Winkel (Grad).
    """
    reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
    full_text = ""
    for page in reader.pages:
        full_text += page.extract_text() + "\n"

    # Standard-Werte für Fallback
    data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "shooter": "Unbekannt",
        "discipline": "Luftgewehr",
        "total_score": 0.0,
        "series": [],
        "coordinates": []
    }

    # HIER KOMMT DEINE REGEX: 
    # Sucht in der PDF nach Zeilen wie "10.4 135" (Ringzahl und Grad)
    # Passe den Regex an, falls deine Meyton PDF etwas anders formatiert ist.
    # Beispiel: Sucht nach Dezimalzahl (1-10.9), gefolgt von Leerzeichen und Gradzahl (0-359)
    shot_pattern = re.compile(r'([1-9]|10)\.\d\s+(\d{1,3})')
    
    matches = shot_pattern.findall(full_text)
    
    total = 0.0
    for match in matches:
        ring = float(match[0])
        grad = float(match[1])
        
        # --- DEINE VORGEGEBENE METHODE ---
        # 1. Radius berechnen (Luftgewehr: 2.5mm pro Ring, 10.9 ist Zentrum)
        radius_mm = (10.9 - ring) * 2.5
        
        # 2. Grad in Bogenmaß umrechnen
        theta = math.radians(grad)
        
        # 3. X und Y berechnen (0 Grad = Oben/12 Uhr -> sin für X, cos für Y)
        # Wir multiplizieren mit 100, damit die App.py sie im Meyton-Standard (Hundertstel-mm) hat!
        x_val = (radius_mm * math.sin(theta)) * 100
        y_val = (radius_mm * math.cos(theta)) * 100
        
        data["coordinates"].append({
            "ring": ring,
            "x": x_val,
            "y": y_val
        })
        total += ring

    # Einfache 10er Serien-Bildung aus den Treffern
    series = []
    current_serie = 0.0
    for i, shot in enumerate(data["coordinates"]):
        current_serie += shot["ring"]
        if (i + 1) % 10 == 0:
            series.append(round(current_serie, 1))
            current_serie = 0.0
    if current_serie > 0:
        series.append(round(current_serie, 1))

    data["total_score"] = round(total, 1)
    data["series"] = series

    return data
