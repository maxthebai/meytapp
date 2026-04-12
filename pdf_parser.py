import re
import requests
import io
from datetime import datetime
from typing import Optional, Dict, Any
import pdfplumber


def download_pdf(url: str) -> bytes:
    """Download PDF from URL and return raw bytes."""
    _validate_url(url)  # Security: prevent SSRF
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.content


ALLOWED_HOSTS = [
    "www.meyton.com",
    "meyton.com",
]
ALLOWED_IP = "195.201.88.185"
ALLOWED_PATH_PREFIX = "print_"


def _validate_url(url: str) -> None:
    """Validate URL to prevent SSRF attacks."""
    from urllib.parse import urlparse
    import ipaddress

    parsed = urlparse(url)

    # Only allow http/https
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme: {parsed.scheme}. Only http/https allowed.")

    host = parsed.hostname
    if not host:
        raise ValueError("Invalid URL: no hostname found.")

    # Check if host is allowed (either domain or specific IP)
    try:
        ip_str = socket.gethostbyname(host)
    except socket.gaierror:
        raise ValueError(f"Could not resolve hostname: {host}")

    # Allow specific IP with path prefix
    if ip_str == ALLOWED_IP and parsed.path.startswith("/" + ALLOWED_PATH_PREFIX):
        return  # Valid Meyton server URL

    # Check against allowed hosts
    if host not in ALLOWED_HOSTS:
        raise ValueError(f"Host '{host}' is not allowed. Only Meyton URLs accepted.")

    # Check resolved IP is not private/internal
    ip = ipaddress.ip_address(ip_str)
    if ip.is_private or ip.is_loopback or ip.is_reserved:
        raise ValueError(f"Cannot access private/internal IP: {ip_str}")


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract all text from PDF bytes using pdfplumber."""
    pdf_file = io.BytesIO(pdf_bytes)
    text_parts = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
    return "\n".join(text_parts)


def parse_meyton_pdf(text: str) -> Dict[str, Any]:
    """
    Parse Meyton ESTA 5 PDF text and extract shooting data.

    Returns a dictionary with:
    - date: Date string (YYYY-MM-DD)
    - shooter: Name of the shooter
    - discipline: Shooting discipline
    - series: List of individual series scores
    - total_score: Total rings/score
    """
    lines = text.split("\n")

    # Extract date - various formats like "10.03.2024" or "10.03.2024 14:30"
    date_match = re.search(r"(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})", text)
    date_str = ""
    if date_match:
        raw_date = date_match.group(1)
        # Normalize separator and parse
        normalized = re.sub(r"[./-]", ".", raw_date)
        try:
            # Try DD.MM.YYYY format
            parsed = datetime.strptime(normalized, "%d.%m.%Y")
            date_str = parsed.strftime("%Y-%m-%d")
        except ValueError:
            try:
                # Try YYYY-MM-DD
                parsed = datetime.strptime(normalized, "%Y.%m.%d")
                date_str = parsed.strftime("%Y-%m-%d")
            except ValueError:
                date_str = raw_date.replace(".", "-")

    # Extract shooter name - typically after "Schütze:" or similar label
    shooter = ""
    shooter_patterns = [
        r"(?:Schütze|Name)[:\s]+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)+)",
        r"([A-ZÄÖÜ][a-zäöüß]+\s+[A-ZÄÖÜ][a-zäöüß]+)\s+(?:hat|schießt|wird)",
        r"([A-ZÄÖÜ][a-zäöüß]+),\s*([A-ZÄÖÜ][a-zäöüß]+)",  # "Baiker, Max" format
    ]
    for pattern in shooter_patterns:
        match = re.search(pattern, text)
        if match:
            groups = match.groups()
            if len(groups) == 2:
                # "Lastname, Firstname" format - swap to "Firstname Lastname"
                shooter = f"{groups[1].strip()} {groups[0].strip()}"
            else:
                shooter = match.group(1).strip()
            break

    # Extract discipline - common shooting disciplines
    discipline = ""
    discipline_candidates = [
        ("LG", "Luftgewehr"),
        ("LP", "Luftpistole"),
        ("KK", "KK-Gewehr"),
        ("Freie Pistole", "Freie Pistole"),
        ("Standardpistole", "Standardpistole"),
        ("Zentralfeuerpistole", "Zentralfeuerpistole"),
        ("Ordonnanzpistole", "Ordonnanzpistole"),
        ("Revolver", "Revolver"),
        ("Teilsystem", "Teilsystem"),
        ("Muttern", "Muttern"),
        ("Spielmann", "Spielmann")
    ]
    for abbrev, full_name in discipline_candidates:
        if abbrev.lower() in text.lower():
            # Check if it's followed by "20" (number of shots) and append it
            match = re.search(re.escape(abbrev) + r"\s*(\d+)", text, re.IGNORECASE)
            if match:
                discipline = f"{full_name} {match.group(1)}"
            else:
                discipline = full_name
            break

    # Extract series scores - look for patterns like "Serie: 95 94 96 93" or "1: 95 2: 94"
    series = []
    series_patterns = [
        r"(?:Serie[n]?[:\s]+)(\d+(?:\s+\d+)+)",
        r"(\d{2,3})\s+(?:\d{2,3}\s+){0,3}\d{2,3}",  # Ring numbers in a row
        r"Serie\s*1[:\s]+(\d{2,3}).*Serie\s*2[:\s]+(\d{2,3})",
    ]

    for pattern in series_patterns:
        matches = re.findall(pattern, text)
        if matches:
            if isinstance(matches[0], tuple):
                series = [int(m) for m in matches[0] if m.isdigit()]
            else:
                # Find all numbers in the matched string
                numbers = re.findall(r"\d{2,3}", matches[0] if isinstance(matches[0], str) else " ".join(matches))
                if numbers:
                    series = [int(n) for n in numbers[:10]]  # Limit to reasonable number
            if series:
                break

    # If no series found with patterns, try line by line approach
    if not series:
        for line in lines:
            # Look for lines with 2-3 digit numbers that could be scores
            numbers = re.findall(r"\b(\d{2,3})\b", line)
            if 3 <= len(numbers) <= 6 and all(0 <= int(n) <= 100 for n in numbers):
                series = [int(n) for n in numbers]
                break

    # Extract total score - usually at the end or marked with "Gesamt" or "Summe"
    total_score = 0
    total_patterns = [
        r"(?:Gesamt|Summe|Total)[:\s]+(\d{2,3})",
        r"(?:Ergebnis|result)[:\s]+(\d{2,3})",
    ]
    for pattern in total_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            total_score = int(match.group(1))
            break

    # If no explicit total found, calculate from series
    if total_score == 0 and series:
        total_score = sum(series)

    return {
        "date": date_str,
        "shooter": shooter,
        "discipline": discipline,
        "series": series,
        "total_score": total_score,
    }


# Symbol mapping: direction symbols to angles (degrees, 0 = right, clockwise)
DIRECTION_SYMBOLS = {
    # Arrows
    "↑": 270, "→": 0, "↓": 90, "←": 180,
    "↗": 315, "↘": 45, "↙": 135, "↖": 225,
    # Common OCR confusions for "1" and "t" (top indicator often misread)
    "1": 270, "t": 270, "T": 270,
    # Right variants
    "r": 0, "R": 0,
    # Bottom variants
    "v": 90, "V": 90, "^": 270,  # inverted caret sometimes
    # Left variants
    "l": 180, "L": 180,
    # Corner indicators (OCR may read as numbers)
    "7": 315, "9": 45, "3": 135, "1": 270,
}


def parse_shot_values(text: str) -> list[dict]:
    """
    Extract individual shot values and directions from PDF text.

    Looks for patterns like:
    - "Serie 1:" followed by shots like "10.4↑" or "9.5→" etc.
    - Direction symbols: ↑ (top/270°), → (right/0°), ↓ (bottom/90°), ← (left/180°)
    - Also handles OCR confusions: 1/t for top, numbers for corners

    Returns list of dicts: [{"ring": 10.4, "angle": 270}, ...]
    """
    import math
    import random

    shots = []

    # Pattern to find series sections with individual shots
    # Looks for "Serie X:" followed by shot patterns like "10.4↑" or "9.5 1"
    series_pattern = r"Serie\s+(\d+)[:\s]+(.+?)(?=Serie\s+\d+|Gesamt|Summe|$)"
    series_matches = re.findall(series_pattern, text, re.IGNORECASE | re.DOTALL)

    # Fallback: try to find any decimal ring values followed by direction indicators
    if not series_matches:
        # Generic pattern for ring + direction like "10.4↑" or "9.5→"
        shot_pattern = r"(\d+\.?\d*)\s*([↑→↓←↗↘↙↖↔↕1tTlLrR7-9])"
        all_shots = re.findall(shot_pattern, text)
        if all_shots:
            for ring_str, direction in all_shots:
                try:
                    ring = float(ring_str)
                    angle = DIRECTION_SYMBOLS.get(direction, 0)
                    shots.append({"ring": ring, "angle": angle})
                except ValueError:
                    pass

    for series_num, series_content in series_matches:
        # Find all shots in this series: "10.4↑" or "9.5" (no direction = center)
        shot_pattern = r"(\d+\.?\d*)\s*([↑→↓←↗↘↙↖↔↕1tTlLrR7-9])?"
        matches = re.findall(shot_pattern, series_content)

        for ring_str, direction in matches:
            try:
                ring = float(ring_str)
                if ring > 11:  # Invalid ring value
                    continue
                angle = DIRECTION_SYMBOLS.get(direction, 0) if direction else None
                shots.append({
                    "ring": ring,
                    "angle": angle,
                    "series": int(series_num)
                })
            except ValueError:
                continue

    return shots


def calculate_shot_coordinates(shots: list[dict], jitter: float = 3.0) -> list[dict]:
    """
    Calculate X/Y coordinates from ring value and direction.

    Radius (mm) = (10.9 - ring_value) * 2.1
    X = radius * cos(angle)
    Y = radius * sin(angle)
    Adds ±jitter degrees random offset to prevent overlapping shots.
    """
    import math
    import random

    coordinates = []
    for shot in shots:
        ring = shot["ring"]
        angle = shot.get("angle")

        # Calculate radius from ring value
        radius = (10.9 - ring) * 2.1  # mm

        if angle is None:
            # No direction = centered shot
            angle = random.uniform(0, 360)
            jittered = 0
        else:
            # Add random jitter ±jitter degrees
            jittered = random.uniform(-jitter, jitter)
            angle = angle + jittered

        # Convert to radians (0° = right, counter-clockwise for Y flip)
        rad = math.radians(angle)

        # X/Y calculation (Y inverted for screen coordinates)
        x = radius * math.cos(rad)
        y = -radius * math.sin(rad)  # negative because screen Y is inverted

        coordinates.append({
            "ring": ring,
            "angle": angle,
            "jitter": jittered,
            "radius": radius,
            "x": round(x, 2),
            "y": round(y, 2)
        })

    return coordinates


def process_meyton_url(url: str) -> Dict[str, Any]:
    """
    Complete pipeline: Download PDF from URL and extract shooting data.

    Args:
        url: Meyton ESTA 5 QR code URL

    Returns:
        Dictionary with extracted shooting data
    """
    pdf_bytes = download_pdf(url)
    text = extract_text_from_pdf(pdf_bytes)
    data = parse_meyton_pdf(text)

    # Extract shot details with directions
    shots = parse_shot_values(text)
    if shots:
        data["shots"] = shots
        data["coordinates"] = calculate_shot_coordinates(shots)

    return data
