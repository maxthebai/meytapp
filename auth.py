import yaml
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
            "name": "meyton_app_auth_cookie",
            "key": "ein_geheimer_schluessel_123",
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
        cookie_name="meyton_app_auth_cookie",
        cookie_key="ein_geheimer_schluessel_123",
        cookie_expiry_days=30,
        auto_hash=True,
    )

    return authenticator
