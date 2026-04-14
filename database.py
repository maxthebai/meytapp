import os
import uuid
from supabase import create_client, Client
from typing import Optional

def _get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)

def init_db() -> None:
    """No-op: Supabase table must be created manually via SQL (see README)."""
    pass

def save_shooting(
    user_id: str,
    date: str,
    shooter: str,
    discipline: str,
    total_score: int,
    series: str,
    url: Optional[str] = None,
    coordinates: Optional[str] = None,
) -> None:
    client = _get_client()
    client.table("shootings").insert({
        "user_id": user_id,
        "date": date,
        "shooter": shooter,
        "discipline": discipline,
        "total_score": total_score,
        "series": series,
        "url": url,
        "coordinates": coordinates,
    }).execute()

def get_all_shootings(user_id: Optional[str] = None) -> list:
    client = _get_client()
    query = client.table("shootings").select(
        "id, user_id, date, shooter, discipline, total_score, series, url, coordinates, created_at"
    ).order("date", desc=True)
    if user_id:
        query = query.eq("user_id", user_id)
    result = query.execute()
    # Return as list of tuples to match original SQLite format
    rows = []
    for r in result.data:
        rows.append((
            r["id"], r["user_id"], r["date"], r["shooter"],
            r["discipline"], r["total_score"], r["series"],
            r.get("url"), r.get("coordinates"), r.get("created_at")
        ))
    return rows

def delete_shooting(shooting_id: int, user_id: str) -> None:
    client = _get_client()
    client.table("shootings").delete().eq("id", shooting_id).eq("user_id", user_id).execute()

# ---------------------------------------------------------------------------
# Share-Links
# Supabase-Tabelle (einmalig per SQL anlegen):
#   CREATE TABLE shares (
#       token TEXT PRIMARY KEY,
#       shooting_id BIGINT NOT NULL,
#       created_at TEXT DEFAULT (to_char(now(), 'YYYY-MM-DD"T"HH24:MI:SS'))
#   );
# ---------------------------------------------------------------------------

def create_share_token(shooting_id: int) -> str:
    """Erstellt ein Share-Token für eine Schuss-Session. Gibt den Token zurück."""
    token = uuid.uuid4().hex
    client = _get_client()
    client.table("shares").insert({
        "token": token,
        "shooting_id": shooting_id,
    }).execute()
    return token

def get_shooting_by_share_token(token: str) -> Optional[tuple]:
    """Lädt eine Schuss-Session anhand eines Share-Tokens (ohne Auth). Gibt Tuple oder None zurück."""
    client = _get_client()
    share = client.table("shares").select("shooting_id").eq("token", token).execute()
    if not share.data:
        return None
    shooting_id = share.data[0]["shooting_id"]
    result = client.table("shootings").select(
        "id, user_id, date, shooter, discipline, total_score, series, url, coordinates, created_at"
    ).eq("id", shooting_id).execute()
    if not result.data:
        return None
    r = result.data[0]
    return (
        r["id"], r["user_id"], r["date"], r["shooter"],
        r["discipline"], r["total_score"], r["series"],
        r.get("url"), r.get("coordinates"), r.get("created_at"),
    )
