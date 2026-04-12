import PyPDF2
import re
import math
from io import BytesIO
from datetime import datetime

def process_pdf_bytes(pdf_bytes):
    reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"

    # 1. Metadaten extrahieren
    date_match = re.search(r"Datum:\s+(\d{2}\.\d{2}\.\d{4})", text)
    name_match = re.search(r"Name:\s+([^\n]+)", text)
    
    data = {
        "date": date_match.group(1) if date_match else datetime.now().strftime("%d.%m.%Y"),
        "shooter": name_match.group(1).strip() if name_match else "Unbekannt",
        "discipline": "Luftgewehr",
        "total_score": 0.0,
        "series": [],
        "coordinates": []
    }

    # 2. Schüsse finden (Muster: Ringwert gefolgt von Winkel/Grad)
    # Sucht nach: Zahl.Zahl (Ring) und dann einer Zahl (Winkel)
    # Beispiel: "10.4 135"
    shot_pattern = re.compile(r"(\d{1,2}\.\d)\s+(\d{1,3})")
    matches = shot_pattern.findall(text)

    total = 0.0
    for ring_str, grad_str in matches:
        ring = float(ring_str)
        grad = float(grad_str)
        
        # --- MATHEMATISCHE BERECHNUNG ---
        # r = (10.9 - Ring) * 2.5mm
        radius_mm = (10.9 - ring) * 2.5
        theta = math.radians(grad)
        
        # Umrechnung in X/Y (0 Grad = 12 Uhr)
        x = radius_mm * math.sin(theta)
        y = radius_mm * math.cos(theta)
        
        data["coordinates"].append({"ring": ring, "x": x, "y": y})
        total += ring

    # Serien berechnen (immer 10 Schüsse)
    all_rings = [c["ring"] for c in data["coordinates"]]
    for i in range(0, len(all_rings), 10):
        data["series"].append(round(sum(all_rings[i:i+10]), 1))

    data["total_score"] = round(total, 1)
    return data
