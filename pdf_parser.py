import PyPDF2
import fitz  # PyMuPDF
import re
import math
from io import BytesIO
from datetime import datetime


def _extract_arrows(pdf_bytes):
    """
    Extrahiert Richtungspfeile aus den PDF-Grafikobjekten.
    Jeder Pfeil ist ein schwarzes gefülltes Bezier-Shape.
    Gibt eine sortierte Liste von Winkeln zurück (Uhrzeiger, 0°=12 Uhr).
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    arrows = []

    for page in doc:
        for d in page.get_drawings():
            fill = d.get("fill")
            # Schwarze gefüllte Shapes = Richtungspfeile
            if not fill or fill[0] > 0.1:
                continue

            r = d["rect"]
            cx = (r.x0 + r.x1) / 2
            cy = (r.y0 + r.y1) / 2

            # Alle Kontrollpunkte der Bezier-Kurven sammeln
            pts = []
            for item in d["items"]:
                for p in item[1:]:
                    if hasattr(p, "x"):
                        pts.append((p.x, p.y))

            if not pts:
                continue

            # Pfeilspitze = Punkt mit größtem Abstand vom Mittelpunkt
            tip = max(pts, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)

            # Winkel berechnen: PDF-Y ist invertiert → -dy
            dx = tip[0] - cx
            dy = -(tip[1] - cy)
            # Uhrzeiger: 0°=oben (12 Uhr), 90°=rechts, 180°=unten, 270°=links
            angle_clock = (90 - math.degrees(math.atan2(dy, dx))) % 360

            arrows.append({"cx": cx, "cy": cy, "angle": angle_clock})

    # Lesereihenfolge: erst nach Y-Reihe (gerundet auf 20px), dann nach X
    arrows.sort(key=lambda s: (round(s["cy"] / 20) * 20, s["cx"]))
    return arrows


def process_pdf_bytes(pdf_bytes):
    # --- Text-Parsing ---
    reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
    full_text = ""
    for page in reader.pages:
        full_text += page.extract_text() + "\n"

    # --- Disziplin ---
    is_pistole = "Pistole" in full_text or "LP" in full_text
    discipline = "Luftpistole" if is_pistole else "Luftgewehr"

    # Luftgewehr 10m: Ringbreite 2.5mm, Innenzehner-Radius 0.5mm
    # Luftpistole 10m: Ringbreite 8.0mm, Innenzehner-Radius 5.5mm
    if is_pistole:
        ring_step = 8.0
        inner_radius = 5.5
    else:
        ring_step = 2.5
        inner_radius = 0.5

    # --- Datum ---
    date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", full_text)
    date_str = date_match.group(1) if date_match else datetime.now().strftime("%d.%m.%Y")

    # --- Schütze ---
    shooter = "Unbekannt"
    for line in full_text.strip().split("\n")[:8]:
        line = line.strip()
        if re.match(r"^[A-ZÄÖÜa-zäöü][A-ZÄÖÜa-zäöü\s,\-\.]+$", line) and ":" not in line and len(line) > 3:
            shooter = line
            break

    # --- Gesamtergebnis ---
    gesamt_match = re.search(r"Ergebnis:\s+(\d+)\s+\(([0-9.]+)\)", full_text)
    total_score = int(gesamt_match.group(1)) if gesamt_match else 0

    # --- Serien ---
    serien_match = re.search(r"Serien:\s+([\d\s]+)", full_text)
    series = [int(x) for x in serien_match.group(1).strip().split()] if serien_match else []

    # --- Ringwerte aus Serienblöcken ---
    serie_pattern = re.compile(
        r"Serie\s+\d+:.*?\n((?:[0-9]+\.[0-9]\*?\s+){4}[0-9]+\.[0-9]\*?)\s*\n"
        r"((?:[0-9]+\.[0-9]\*?\s+){4}[0-9]+\.[0-9]\*?)"
    )
    rings = []
    for m in serie_pattern.finditer(full_text):
        for line in [m.group(1), m.group(2)]:
            for v in line.strip().split():
                rings.append(float(v.replace("*", "")))

    # --- Pfeile (Winkel) aus Grafikdaten ---
    arrows = _extract_arrows(pdf_bytes)

    # --- Koordinaten zusammenführen ---
    coordinates = []
    n = min(len(rings), len(arrows))

    for i in range(n):
        ring = rings[i]
        angle_clock = arrows[i]["angle"]

        # Radius: Mitte des zugehörigen Ringbands
        # Ring 10.9 (Innenzehner) → r ≈ 0, Ring 10.0 → r = inner_radius + 0.5*ring_step
        radius_mid = max(0.0, (10.9 - ring) * ring_step + inner_radius)

        theta = math.radians(angle_clock)
        x = round(radius_mid * math.sin(theta), 2)   # sin weil 0°=oben
        y = round(radius_mid * math.cos(theta), 2)   # cos weil 0°=oben

        coordinates.append({"ring": ring, "x": x, "y": y})

    return {
        "date": date_str,
        "shooter": shooter,
        "discipline": discipline,
        "total_score": total_score,
        "series": series,
        "coordinates": coordinates,
    }
