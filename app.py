import streamlit as st
import pandas as pd
import json
import matplotlib.pyplot as plt
import numpy as np
import cv2
from datetime import datetime

# Eigene Module (Stelle sicher, dass diese Dateien im Ordner sind!)
from database import init_db, save_shooting, get_all_shootings, delete_shooting
from pdf_parser import process_meyton_url, process_pdf_bytes
from auth import init_auth

# --- KONFIGURATION ---
st.set_page_config(page_title="Meytapp 🎯", layout="wide")

# --- GRAFIK FUNKTION (MATPLOTLIB) ---
def create_target_plot(coordinates: list[dict]):
    """Erstellt eine exakte ISSF Luftgewehrscheibe (Maßstab in mm)."""
    fig, ax = plt.subplots(figsize=(6, 6))
    
    # ISSF Radien für LG (in mm)
    # Ring 1 (außen) bis Ring 9 (innen)
    ring_radii = {1: 22.75, 2: 20.25, 3: 17.75, 4: 15.25, 
                  5: 12.75, 6: 10.25, 7: 7.75, 8: 5.25, 9: 2.75}
    
    # 1. Ringe zeichnen
    for r, radius in sorted(ring_radii.items()):
        # Spiegel ab Ring 4 ist schwarz
        is_spiegel = r >= 4
        f_color = 'black' if is_spiegel else 'white'
        e_color = 'white' if is_spiegel else 'black'
        
        circle = plt.Circle((0, 0), radius, edgecolor=e_color, facecolor=f_color, zorder=1)
        ax.add_patch(circle)
        
        # Ringzahlen (auf der vertikalen Achse oben und unten)
        t_color = 'white' if is_spiegel else 'black'
        ax.text(0, radius - 1.5, str(r), color=t_color, ha='center', va='center', fontsize=7, zorder=2)
        ax.text(0, -radius + 1.5, str(r), color=t_color, ha='center', va='center', fontsize=7, zorder=2)

    # 2. Die Zehn (Zentraler weißer Punkt, Radius 0.25mm)
    ax.add_patch(plt.Circle((0, 0), 0.25, color='white', zorder=3))

    # 3. Treffer zeichnen
    if coordinates:
        for shot in coordinates:
            # WICHTIG: Umrechnung von Hundertstel-mm in mm (Meyton Standard)
            x = shot.get("x", 0) / 100.0
            y = shot.get("y", 0) / 100.0
            ring = shot.get("ring", 0)

            # Farb-Logik
            if ring >= 10.0:
                c = 'red'
            elif ring >= 9.0:
                c = 'yellow'
            else:
                c = 'black'
            
            # Weißer Rand für schwarze Treffer auf schwarzem Spiegel
            edge = 'white' if c == 'black' and abs(x) < 15.5 else 'black'
            ax.scatter(x, y, color=c, edgecolors=edge, s=60, alpha=0.9, zorder=5, linewidth=0.5)

    ax.set_xlim(-25, 25)
    ax.set_ylim(-25, 25)
    ax.set_aspect('equal')
    ax.axis('off')
    plt.tight_layout()
    return fig

# --- QR SCANNER ---
def scan_qr(img):
    from pyzbar.pyzbar import decode
    decoded = decode(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    return decoded[0].data.decode("utf-8") if decoded else None

# --- AUTH & DB ---
init_db()
if "authenticator" not in st.session_state:
    st.session_state.authenticator = init_auth()

auth = st.session_state.authenticator
auth.login(location="main")

if st.session_state.get("authentication_status") is not True:
    if st.session_state.get("authentication_status") is False:
        st.error("Login fehlgeschlagen")
    t1, t2 = st.tabs(["Anmelden", "Registrieren"])
    with t2:
        auth.register_user(location="main", merge_username_email=True)
    st.stop()

# --- APP LAYOUT ---
username = st.session_state.username
st.sidebar.subheader(f"User: {st.session_state.name}")
auth.logout(location="sidebar")

tabs = st.tabs(["📥 Import", "📋 Historie", "📈 Verlauf", "🎯 Detail"])

# --- TAB 1: IMPORT (Kamera, URL, PDF) ---
with tabs[0]:
    mode = st.radio("Quelle wählen", ["Kamera", "Link/URL", "PDF Datei"], horizontal=True)
    if mode == "Kamera":
        cam_img = st.camera_input("QR-Code scannen")
        if cam_img:
            file_bytes = np.frombuffer(cam_img.read(), np.uint8)
            decoded_url = scan_qr(cv2.imdecode(file_bytes, cv2.IMREAD_COLOR))
            if decoded_url:
                st.success(f"Gefunden: {decoded_url}")
                if st.button("Jetzt importieren"):
                    data = process_meyton_url(decoded_url)
                    save_shooting(username, data["date"], data["shooter"], data["discipline"], 
                                 data["total_score"], ",".join(map(str, data["series"])), decoded_url, json.dumps(data.get("coordinates", [])))
                    st.rerun()
    elif mode == "Link/URL":
        url = st.text_input("Meyton URL einfügen")
        if st.button("Laden"):
            data = process_meyton_url(url)
            save_shooting(username, data["date"], data["shooter"], data["discipline"], data["total_score"], ",".join(map(str, data["series"])), url, json.dumps(data.get("coordinates", [])))
            st.rerun()
    else:
        pdf = st.file_uploader("PDF hochladen", type="pdf")
        if pdf:
            data = process_pdf_bytes(pdf.read())
            save_shooting(username, data["date"], data["shooter"], data["discipline"], data["total_score"], ",".join(map(str, data["series"])), None, json.dumps(data.get("coordinates", [])))
            st.success("PDF gespeichert!")

# --- TAB 3: VERLAUF (FIX: KEINE UHRZEIT) ---
with tabs[2]:
    data = get_all_shootings(username)
    if len(data) > 1:
        import plotly.express as px
        df = pd.DataFrame(data, columns=["ID", "User", "Datum", "Schütze", "Disziplin", "Gesamt", "Serien", "URL", "Coords", "Erstellt"])
        # Fix: Datum ohne Zeit anzeigen
        df["Datum"] = pd.to_datetime(df["Datum"]).dt.date
        fig = px.line(df.sort_values("Datum"), x="Datum", y="Gesamt", markers=True, title="Deine Entwicklung")
        fig.update_xaxes(tickformat="%d.%m.%Y") # Deutsches Format
        st.plotly_chart(fig, use_container_width=True)

# --- TAB 4: DETAIL (FIX: MASSSTAB) ---
with tabs[3]:
    data = get_all_shootings(username)
    if data:
        options = {s[0]: f"{s[2]} - {s[3]} ({s[5]} Ringe)" for s in data}
        sel = st.selectbox("Ergebnis wählen", options.keys(), format_func=lambda x: options[x])
        res = next(s for s in data if s[0] == sel)
        coords = json.loads(res[8]) if res[8] else []
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.pyplot(create_target_plot(coords))
        with c2:
            st.metric("Gesamt", res[5])
            st.caption(f"Datum: {res[2]}")
            st.caption(f"Schütze: {res[3]}")
