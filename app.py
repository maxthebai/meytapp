import streamlit as st
import plotly.express as px
from datetime import datetime

from database import init_db, save_shooting, get_all_shootings, delete_shooting
from pdf_parser import process_meyton_url
from auth import init_auth


def init_session():
    """Initialize session state variables."""
    if "authenticator" not in st.session_state:
        st.session_state.authenticator = init_auth()
    if "db_initialized" not in st.session_state:
        init_db()
        st.session_state.db_initialized = True


def import_result(url: str, user_id: str):
    """Process and save a Meyton URL result."""
    with st.spinner("PDF wird heruntergeladen und verarbeitet..."):
        try:
            data = process_meyton_url(url)

            if data["shooter"] and data["total_score"] > 0:
                series_str = ",".join(str(s) for s in data["series"])
                save_shooting(
                    user_id=user_id,
                    date=data["date"],
                    shooter=data["shooter"],
                    discipline=data["discipline"],
                    total_score=data["total_score"],
                    series=series_str,
                    url=url
                )
                st.success(f"Ergebnis für {data['shooter']} wurde gespeichert!")
                st.balloons()
                return True
            else:
                st.warning("PDF gefunden, aber Daten konnten nicht vollständig extrahiert werden.")
                st.json(data)
                return False
        except Exception as e:
            st.error(f"Fehler beim Verarbeiten der URL: {str(e)}")
            return False


st.set_page_config(
    page_title="Meytapp - Schießergebnisse",
    page_icon="🎯",
    layout="wide"
)

init_session()
authenticator = st.session_state.authenticator

# ── Authentication ────────────────────────────────────────────────────────────

if "authentication_status" not in st.session_state:
    st.session_state.authentication_status = None
if "username" not in st.session_state:
    st.session_state.username = None
if "name" not in st.session_state:
    st.session_state.name = None

# Login / Register tabs - only shown when not authenticated
if st.session_state.authentication_status is None or st.session_state.authentication_status is False:
    tab_login, tab_register = st.columns(2)

    with tab_login:
        st.subheader("Anmelden")
        login_result = authenticator.login(
            location="main",
            max_login_attempts=5,
            fields={
                'Form name': 'Anmelden',
                'Username': 'E-Mail',
                'Password': 'Passwort',
                'Login': 'Anmelden',
            }
        )
        if login_result:
            st.session_state.name, st.session_state.authentication_status, st.session_state.username = login_result

    with tab_register:
        st.subheader("Neuen Account erstellen")
        try:
            reg_result = authenticator.register_user(
                location="main",
                pre_authorized=None,
                captcha=False,
                merge_username_email=True,
                fields={
                    'Form name': 'Registrieren',
                    'First name': 'Vorname',
                    'Last name': 'Nachname',
                    'Email': 'E-Mail',
                    'Password': 'Passwort',
                    'Repeat password': 'Passwort wiederholen',
                    'Register': 'Account erstellen',
                }
            )
            # After successful registration, automatically log in the user
            if reg_result and reg_result[0] is not None:
                email = reg_result[0]
                username_reg = reg_result[1]
                name_reg = reg_result[2]
                # Get password from form input - use the same fields structure
                st.session_state.reg_email = email
                st.session_state.reg_username = username_reg
                st.session_state.reg_name = name_reg
        except Exception as e:
            st.error(f"Fehler: {e}")

    # Auto-login after registration
    if "reg_email" in st.session_state and st.session_state.get("reg_email"):
        email = st.session_state.reg_email
        # Show login form for re-authentication with password
        st.subheader("Bitte Passwort zur Bestätigung eingeben")
        confirm_password = st.text_input("Passwort", type="password", key="confirm_password")
        if st.button("Anmelden", type="primary"):
            # Use the authenticator's authentication controller to log in
            if st.session_state.authenticator.authentication_controller.login(
                email, confirm_password, max_login_attempts=5
            ):
                st.session_state.name = st.session_state.reg_name
                st.session_state.authentication_status = True
                st.session_state.username = st.session_state.reg_username
                # Clean up registration state
                for key in ['reg_email', 'reg_username', 'reg_name', 'confirm_password']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
            else:
                st.error("Passwort falsch. Bitte versuche es erneut.")
        st.stop()

if st.session_state.authentication_status is False:
    st.error("Benutzername oder Passwort falsch.")
elif st.session_state.authentication_status is None:
    st.stop()

# Logged-in state
username = st.session_state.username
user_name = st.session_state.name

st.title(f"🎯 Meytapp - Willkommen, {user_name}!")
st.markdown(f"Angemeldet als **{username}**.")
authenticator.logout(location="sidebar")
st.divider()

# ── Main App ───────────────────────────────────────────────────────────────────

# Import Section with Tabs
st.header("Ergebnis importieren")

tab1, tab2 = st.tabs(["📋 URL eingeben", "📷 QR-Code scannen"])

with tab1:
    url_input = st.text_input(
        "Meyton QR-Code URL",
        placeholder="https://example.com/esta5/...",
        help="Füge die URL aus dem Meyton ESTA 5 QR-Code hier ein.",
        key="url_input"
    )

    if st.button("Ergebnis importieren", type="primary", use_container_width=True):
        if url_input:
            import_result(url_input, username)
        else:
            st.warning("Bitte eine URL eingeben.")

with tab2:
    st.markdown("""
        **So funktioniert's:**
        1. Aktiviere die Kamera mit dem Button unten
        2. Halte den QR-Code vor die Kamera
        3. Die URL wird automatisch erkannt und verarbeitet
    """)

    # Session-State initialisieren
    if "qr_result" not in st.session_state:
        st.session_state.qr_result = None
    if "show_upload" not in st.session_state:
        st.session_state.show_upload = False

    # Fallback-Upload Button
    col_cam, col_upload = st.columns([1, 1])
    with col_cam:
        if st.button("📷 Kamera starten", use_container_width=True):
            st.session_state.show_upload = False
    with col_upload:
        if st.button("📁 Bild hochladen", use_container_width=True):
            st.session_state.show_upload = True

    if st.session_state.show_upload:
        st.info("Lade ein Bild mit QR-Code hoch")
        uploaded_file = st.file_uploader(
            "Bild auswählen", type=["png", "jpg", "jpeg"], key="qr_upload"
        )
        if uploaded_file:
            import cv2
            import numpy as np
            file_bytes = np.frombuffer(uploaded_file.read(), dtype=np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            detector = cv2.QRCodeDetector()
            data, _, _ = detector.detectAndDecode(img)
            if data and "esta" in data.lower():
                st.session_state.qr_result = data
            elif data:
                st.warning(f"QR-Code gefunden, aber kein gültiger Meyton-Code: {data}")
            else:
                st.error("Kein QR-Code im Bild gefunden.")

    else:
        try:
            from streamlit_webrtc import webrtc_streamer, WebRtcMode
            from streamlit_webrtc.models import VideoProcessorBase
            import cv2
            import queue

            if "qr_queue" not in st.session_state:
                st.session_state.qr_queue = queue.Queue()

            class QRVideoProcessor(VideoProcessorBase):
                def recv(self, frame):
                    img = frame.to_ndarray(format="bgr24")
                    detector = cv2.QRCodeDetector()
                    data, _, _ = detector.detectAndDecode(img)
                    if data and "esta" in data.lower():
                        st.session_state.qr_queue.put(data)
                    return frame

            ctx = webrtc_streamer(
                key="qr-scanner",
                mode=WebRtcMode.SENDRECV,
                video_processor_factory=QRVideoProcessor,
                media_stream_constraints={"video": {"facingMode": "environment"}},
                async_processing=True,
            )

            if ctx.state.playing:
                st.info("📷 Suche nach QR-Code... Halte ihn vor die Kamera")

            # Nicht-blockierend Queue prüfen (kein while True!)
            if not st.session_state.qr_queue.empty():
                try:
                    qr_data = st.session_state.qr_queue.get_nowait()
                    st.session_state.qr_result = qr_data
                    st.session_state.qr_queue = queue.Queue()  # Reset queue
                except queue.Empty:
                    pass

        except ImportError:
            st.error("Kamera-Bibliothek nicht verfügbar. Bitte nutze 'Bild hochladen'.")

    # Ergebnis-Anzeige (funktioniert für beide Methoden)
    if st.session_state.qr_result:
        st.success(f"QR-Code erkannt: {st.session_state.qr_result}")
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("Ergebnis importieren", type="primary", use_container_width=True):
                success = import_result(st.session_state.qr_result, username)
                if success:
                    st.session_state.qr_result = None
                    st.rerun()
        with c2:
            if st.button("Neu scannen", type="secondary", use_container_width=True):
                st.session_state.qr_result = None
                st.rerun()

# Display all shootings for this user
st.header("Schießhistorie")

shootings = get_all_shootings(user_id=username)

if shootings:
    import pandas as pd

    df = pd.DataFrame(
        shootings,
        columns=["ID", "Benutzer", "Datum", "Schütze", "Disziplin", "Gesamt", "Serien", "URL", "Erstellt"]
    )

    df_display = df.copy()
    df_display["Serien"] = df_display["Serien"].apply(
        lambda x: x if len(str(x)) <= 20 else str(x)[:20] + "..."
    )

    col_show, col_del = st.columns([4, 1])
    with col_show:
        st.dataframe(
            df_display[["Datum", "Schütze", "Disziplin", "Gesamt", "Serien"]],
            use_container_width=True,
            hide_index=True
        )

    if len(shootings) >= 2:
        st.header("Entwicklung der Ringzahl")

        df_chart = df.copy()
        df_chart["Datum"] = pd.to_datetime(df_chart["Datum"], errors="coerce")
        df_chart = df_chart.sort_values("Datum")

        fig = px.line(
            df_chart,
            x="Datum",
            y="Gesamt",
            color="Schütze",
            markers=True,
            title="Gesamtringzahl über die Zeit"
        )
        fig.update_layout(
            xaxis_title="Datum",
            yaxis_title="Ringe",
            legend_title="Schütze",
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_del:
        st.markdown("### Löschen")
        delete_id = st.number_input(
            "ID zum Löschen",
            min_value=1,
            max_value=int(df["ID"].max()) if len(df) > 0 else 1,
            step=1,
            key="delete_id"
        )
        if st.button("Löschen", type="secondary"):
            delete_shooting(int(delete_id), username)
            st.rerun()
else:
    st.info("Noch keine Schießergebnisse gespeichert. Importiere ein Ergebnis über die URL oben.")


