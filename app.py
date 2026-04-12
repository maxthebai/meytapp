import streamlit as st
import pandas as pd
import json
import matplotlib.pyplot as plt
import numpy as np
import cv2
from datetime import datetime

# Eigene Module
from database import init_db, save_shooting, get_all_shootings, delete_shooting
from pdf_parser import process_meyton_url, process_pdf_bytes
from auth import init_auth

# --- KONFIGURATION ---
st.set_page_config(page_title="Meytapp 🎯", layout="wide")

# --- GRAFIK LOGIK (Maßstab 1:1 in mm) ---
def create_target_plot(coordinates: list[dict]):
    """Erstellt eine ISSF-konforme LG-Scheibe."""
    fig, ax = plt.subplots(figsize=(5, 5), dpi=100) # Kleinere, schärfere Vorschau
    
    # ISSF Radien für Luftgewehr (in mm)
    ring_radii = {1: 22.75, 2: 20.25, 3: 17.75, 4: 15.25, 
                  5: 12.75, 6: 10.25, 7: 7.75, 8: 5.25, 9: 2.75}
    
    # 1. Ringe zeichnen
    for r, radius in sorted(ring_radii.items()):
        f_color = 'black' if r >= 4 else 'white'
        e_color = 'white' if r >= 4 else 'black'
        
        circle = plt.Circle((0, 0), radius, edgecolor=e_color, facecolor=f_color, zorder=1)
        ax.add_patch(circle)
        
        # Ringzahlen
        t_color = 'white' if r >= 4 else 'black'
        ax.text(0, radius - 1.2, str(r), color=t_color, ha='center', fontsize=6, zorder=2)
        ax.text(0, -radius + 0.2, str(r), color=t_color, ha='center', fontsize=6, zorder=2)

    # 2. Die Zehn (Massiver weißer Punkt)
    ax.add_patch(plt.Circle((0, 0), 0.25, color='white', zorder=3))

    # 3. Treffer zeichnen
    if coordinates:
        for shot in coordinates:
            # FIX: Meyton liefert Hundertstel-mm -> Umrechnung in mm
            x = shot.get("x", 0) / 100.0
            y = shot.get("y", 0) / 100.0
            ring = shot.get("ring", 0)

            # Farbe nach Wert
            if ring >= 10.0:
                c = 'red'
            elif ring >= 9.0:
                c = 'yellow'
            else:
                c = 'black'
            
            # Rand für Sichtbarkeit auf Schwarz
            edge = 'white' if c == 'black' and abs(x) < 15.5 else 'black'
            ax.scatter(x, y, color=c, edgecolors=edge, s=50, alpha=0.9, zorder=5, linewidth=0.5)

    ax.set_xlim(-25, 25)
    ax.set_ylim(-25, 25)
    ax.set_aspect('equal')
    ax.axis('off')
    plt.tight_layout()
    return fig

# --- QR HELPER ---
def scan_qr(img):
    from pyzbar.pyzbar import decode
    decoded = decode(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    return decoded[0].data.decode("utf-8") if decoded else None

# --- INITIALISIERUNG ---
init_db()
if "authenticator" not in st.session_state:
    st.session_state.authenticator = init_auth()

auth = st.session_state.authenticator
auth.login(location="main")

# Login / Register Logic
if st.session_state.get("authentication_status") is not True:
    t1, t2 = st.tabs(["Anmelden", "Registrieren"])
    with t2:
        auth.register_user(location="main", merge_username_email=True)
    st.stop()

# --- HAUPTANSICHT ---
username = st.session_state.username
st.sidebar.title(f"🎯 {st.session_state.name}")
auth.logout(location="sidebar")

tabs = st.tabs(["📥 Import", "📋 Historie", "📈 Verlauf", "🎯 Detail"])

# 1. IMPORT
with tabs[0]:
    st.subheader("Neues Ergebnis hinzufügen")
    c1, c2, c3 = st.columns([1, 2, 1]) # Macht den Scanner in der Mitte kleiner
    with c2:
        cam_img = st.camera_input("QR scannen")
        if cam_img:
            file_bytes = np.frombuffer(cam_img.read(), np.uint8)
            url = scan_qr(cv2.imdecode(file_bytes, cv2.IMREAD_COLOR))
            if url:
                st.success("Link erkannt!")
                if st.button("Daten jetzt abrufen"):
                    d = process_meyton_url(url)
                    save_shooting(username, d["date"], d["shooter"], d["discipline"], d["total_score"], ",".join(map(str, d["series"])), url, json.dumps(d.get("coordinates", [])))
                    st.rerun()

    st.divider()
    url_input = st.text_input("Oder Link manuell einfügen")
    if st.button("Link laden"):
        d = process_meyton_url(url_input)
        save_shooting(username, d["date"], d["shooter"], d["discipline"], d["total_score"], ",".join(map(str, d["series"])), url_input, json.dumps(d.get("coordinates", [])))
        st.rerun()

# 2. HISTORIE (Wieder da!)
with tabs[1]:
    st.header("Deine gespeicherten Schießen")
    data = get_all_shootings(username)
    if data:
        df = pd.DataFrame(data, columns=["ID", "User", "Datum", "Schütze", "Disziplin", "Gesamt", "Serien", "URL", "Coords", "Erstellt"])
        st.dataframe(df[["ID", "Datum", "Schütze", "Gesamt", "Disziplin"]].sort_values("ID", ascending=False), use_container_width=True, hide_index=True)
        
        with st.expander("🗑️ Eintrag löschen"):
            del_id = st.number_input("ID eingeben", min_value=1, step=1)
            if st.button("Löschen bestätigen"):
                delete_shooting(del_id, username)
                st.rerun()
    else:
        st.info("Noch keine Daten vorhanden.")

# 3. VERLAUF (Ohne Uhrzeit)
with tabs[2]:
    data = get_all_shootings(username)
    if len(data) > 1:
        import plotly.express as px
        df = pd.DataFrame(data, columns=["ID", "User", "Datum", "Schütze", "Disziplin", "Gesamt", "Serien", "URL", "Coords", "Erstellt"])
        # Fix: Uhrzeit abschneiden
        df["Datum"] = pd.to_datetime(df["Datum"]).dt.date 
        fig = px.line(df.sort_values("Datum"), x="Datum", y="Gesamt", markers=True)
        fig.update_xaxes(tickformat="%d.%m.%y") # Sauberes Format
        st.plotly_chart(fig, use_container_width=True)

# 4. DETAIL
with tabs[3]:
    data = get_all_shootings(username)
    if data:
        options = {s[0]: f"{s[2]} - {s[5]} Ringe" for s in data}
        sel = st.selectbox("Auswahl", options.keys(), format_func=lambda x: options[x])
        res = next(s for s in data if s[0] == sel)
        
        col_target, col_info = st.columns([1.5, 1])
        with col_target:
            st.pyplot(create_target_plot(json.loads(res[8]) if res[8] else []))
        with col_info:
            st.metric("Ergebnis", res[5])
            st.write(f"**Disziplin:** {res[4]}")
            st.write(f"**Datum:** {res[2]}")
            st.caption(f"Serien: {res[6]}")
