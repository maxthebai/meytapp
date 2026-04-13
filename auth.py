import os
import json
import yaml
from pathlib import Path
from supabase import create_client, Client
import streamlit_authenticator as st_auth
from streamlit_authenticator import Authenticate

def _get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)

def _load_credentials_from_supabase() -> dict:
    """Load user credentials from Supabase and return in streamlit-authenticator format."""
    client = _get_client()
    result = client.table("users").select("username, name, password, email").execute()
    usernames = {}
    for u in result.data:
        usernames[u["username"]] = {
            "name": u["name"],
            "password": u["password"],  # already hashed
            "email": u.get("email", ""),
        }
    return {"usernames": usernames}

def _save_credentials_to_supabase(credentials: dict) -> None:
    """Persist updated credentials (after register/password change) back to Supabase."""
    client = _get_client()
    for username, data in credentials["usernames"].items():
        # streamlit-authenticator may use 'name' or 'first_name'+'last_name'
        name = (
            data.get("name")
            or f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
            or username
        )
        client.table("users").upsert({
            "username": username,
            "name": name,
            "password": data.get("password", data.get("hashed_password", "")),
            "email": data.get("email", ""),
        }, on_conflict="username").execute()

def init_auth() -> Authenticate:
    """
    Initialize authenticator backed by Supabase.
    Credentials are loaded from the 'users' table and written back after changes.
    """
    credentials = _load_credentials_from_supabase()

    # Write a temporary yaml for streamlit-authenticator (it needs a file path)
    tmp_path = Path("/tmp/credentials.yaml")
    config = {
        "cookie": {
            "name": "meyton_app_auth_cookie",
            "key": os.environ.get("AUTH_COOKIE_KEY", "fallback_secret_key_change_me"),
            "expiry_days": 30.0,
        },
        "credentials": credentials,
    }
    tmp_path.write_text(yaml.dump(config))

    authenticator = Authenticate(
        credentials=str(tmp_path),
        cookie_name="meyton_app_auth_cookie",
        cookie_key=os.environ.get("AUTH_COOKIE_KEY", "fallback_secret_key_change_me"),
        cookie_expiry_days=30,
        auto_hash=True,
    )

    # Monkey-patch: after login/register, sync back to Supabase
    _original_register = authenticator.register_user

    def _register_and_sync(*args, **kwargs):
        result = _original_register(*args, **kwargs)
        # Reload yaml and push to Supabase
        updated = yaml.safe_load(tmp_path.read_text())
        _save_credentials_to_supabase(updated["credentials"])
        return result

    authenticator.register_user = _register_and_sync
    return authenticator
