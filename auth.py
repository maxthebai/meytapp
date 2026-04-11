import yaml
import os
from pathlib import Path
import streamlit_authenticator as st_auth
from streamlit_authenticator import Hasher, Authenticate


def get_credentials_path() -> Path:
    """Return path to the credentials YAML file."""
    return Path("credentials.yaml")


def _get_default_config() -> dict:
    """Return the default credentials/config structure."""
    return {
        "cookie": {
            "name": "meytapp_auth",
            "key": "meytapp_secret_key_change_in_production_abc123",
            "expiry_days": 30.0,
        },
        "credentials": {
            "usernames": {}
        }
    }


def init_auth() -> Authenticate:
    """
    Initialize and return the authenticator.
    Creates a default credentials file if none exists.
    """
    credentials_path = get_credentials_path()

    if not credentials_path.exists():
        credentials_path.write_text(yaml.dump(_get_default_config()))

    credentials = str(credentials_path)

    authenticator = Authenticate(
        credentials=credentials,
        cookie_name="meytapp_auth",
        cookie_key="meytapp_secret_key_change_in_production_abc123",
        cookie_expiry_days=30,
        auto_hash=True,
    )

    return authenticator
