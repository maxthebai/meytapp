import PyPDF2
import re
import math
from io import BytesIO
from datetime import datetime

def process_pdf_bytes(pdf_bytes):
    reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
    full_text = ""
    for page in reader.pages:
        full_text += page.extract_text() + "\n"

    # Disziplin-Check (LP vs LG)
    is_pistole = "Pistole" in full_text
    multiplier = 8.0 if is_pistole else 2.5
    discipline = "Luftpistole" if is_pistole else "Luftgewehr"

    # Metadaten
    date_match = re.search(r"Datum:\s+(\d{2}\.\d{2}\.\d{4})", full_text)
    name_match = re.search(r"Name:\s+([^\n]+)", full_text)
    
    data = {
        "date": date_match.group(1) if date_match else datetime.now().strftime("%d.%m.%Y"),
        "shooter": name_match.group(1).strip() if name_match else "Unbekannt",
        "discipline": discipline,
        "total_score": 0.0,
        "series": [],
        "coordinates": []
    }

    # REGEX-FIX: Wir suchen jetzt nach Schussnummer, Ringwert und Winkel
    # Das Format ist oft: "1 10.2 145" oder nur "10.2 145"
    # Wir suchen nach einer Dezimalzahl (Ring) gefolgt von einer Ganzzahl (Winkel)
    shot_pattern = re.compile(r"(\d{1,2}\.\d)\s+(\d{1,3})")
    matches = shot_pattern.findall(full_text)

    total = 0.0
    temp_rings = []
    
    for ring_str, grad_str in matches:
        ring = float(ring_str)
        grad = float(grad_str)
        
        # Umrechnung in echte mm (Keine Meyton-Interna, reiner PDF-Maßstab)
        # r = (10.9 - Ring) * Multiplikator (2.5 für LG, 8.0 für LP)
        radius_mm = (10.9 - ring) * multiplier
        theta = math.radians(grad)
        
        # X/Y Koordinaten (0 Grad = 12 Uhr)
        x = radius_mm * math.sin(theta)
        y = radius_mm * math.cos(theta)
        
        data["coordinates"].append({"ring": ring, "x": x, "y": y})
        total += ring
        temp_rings.append(ring)

    # Serienbildung (10er Blöcke)
    for i in range(0, len(temp_rings), 10):
        data["series"].append(round(sum(temp_rings[i:i+10]), 1))

    data["total_score"] = round(total, 1)
    return data
