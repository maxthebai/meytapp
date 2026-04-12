import streamlit as st
import pandas as pd
import json
import matplotlib.pyplot as plt
import numpy as np
import cv2
import math
from datetime import datetime

# Eigene Module
from database import init_db, save_shooting, get_all_shootings, delete_shooting
from pdf_parser import process_meyton_url, process_pdf_bytes
from auth import init_auth

# --- KONFIGURATION ---
st.set_page_config(page_title="Meytapp Pro 🎯", layout="wide")

# --- MATHEMATISCHE BERECHNUNG (Ring & Grad -> X/Y) ---
def calculate_coords_from_ring_grad(ring, grad):
    """
    Berechnet X/Y exakt nach Benutzervorgabe:
    Radius = (10.9 - Ring) * 2.5mm
    Winkel in Grad -> Radian -> Sin/Cos
    """
    radius_mm = (10.9 - ring) * 2.5
    theta = math.radians(grad)
    
    # 0 Grad ist bei Meyton oben (12 Uhr)
    x = radius_mm * math.sin(theta)
    y = radius_mm * math.cos(theta)
    
    # Rückgabe in Hundertstel-mm für Datenbank-Kompatibilität
    return x * 100, y * 100

# --- GRAFIK FUNKTION ---
def create_target_plot(coordinates: list[dict]):
    fig, ax = plt.subplots(figsize=(5, 5))
    
    # ISSF Radien LG (mm)
    ring_radii = {1: 22.75, 2: 20.25, 3: 17.75, 4: 15.25, 
                  5: 12.75, 6: 10.25, 7: 7.75, 8: 5.25, 9: 2.75}
    
    for r, radius in sorted(ring_radii.items()):
        f_color = 'black' if r >= 4 else 'white'
        e_color = 'white' if r >= 4 else 'black'
        ax.add_patch(plt.Circle((0, 0), radius, edgecolor=e_color, facecolor=f_color, zorder=1))
        
        t_color = 'white' if r >= 4 else 'black'
        ax.text(0, radius - 1.2, str(r), color=t_color, ha='center', fontsize=7, zorder=2)

    ax.add_patch(plt.Circle((0, 0), 0.25, color='white', zorder=3)) # Die 10

    if coordinates:
        for shot in coordinates:
            # Umrechnung zurück in mm für den Plot
            x, y = shot.get("x", 0) / 100.0, shot.get("y", 0) / 100.0
            ring = shot.get("ring", 0)
            c = 'red' if ring >= 10.0 else ('yellow' if ring >= 9.0 else 'black')
            edge = 'white' if c == 'black' and abs(x) < 15.5 else 'black'
            ax.scatter(x, y, color=c, edgecolors=edge, s=55, alpha=0.9, zorder=5)

    ax.set_xlim(-25, 25); ax.set_ylim(-25, 25)
    ax.set_aspect('equal'); ax.axis('off')
    plt.tight_layout()
    return fig

# --- INITIALISIERUNG & AUTH ---
init_db()
if "authenticator" not in st.session_state:
    st.session_state.authenticator = init_auth()

auth = st.session_state.authenticator
auth.login(location="main")

if st.session_state.get("authentication_status") is not True:
    t1, t2 = st.tabs(["Anmelden", "Registrieren"])
    with t2: auth.register_user(location="main", merge_username_email=True)
    st.stop()

# --- HAUPTAPP ---
username = st.session_state.username
st.sidebar.title(f"🎯 {st.session_state.name}")
auth.logout(location="sidebar")

tabs = st.tabs(["📥 Import", "📋 Historie", "📈 Verlauf", "🎯 Detail"])

# --- TAB 1: IMPORT (QR KLEINER & PDF FIX) ---
with tabs[0]:
    col_left, col_mid, col_right = st.columns([1, 1.5, 1])
    with col_mid:
        st.subheader("QR-Scanner")
        cam_img = st.camera_input("QR-Code scannen", label_visibility="collapsed")
        if cam_img:
            # QR-Logik hier einfügen (wie zuvor mit pyzbar)
            st.info("Scanner aktiv...")

    st.divider()
    
    col_pdf, col_url = st.columns(2)
    with col_pdf:
        st.subheader("PDF manuell")
        uploaded_pdf = st.file_uploader("Meyton PDF hochladen", type="pdf")
        if st.button("PDF verarbeiten") and uploaded_pdf:
            data = process_pdf_bytes(uploaded_pdf.read())
            save_shooting(username, data["date"], data["shooter"], data["discipline"], 
                         data["total_score"], ",".join(map(str, data["series"])), None, json.dumps(data.get("coordinates", [])))
            st.success("Gespeichert!")
            st.rerun()

    with col_url:
        st.subheader("URL Import")
        url_in = st.text_input("Meyton Link")
        if st.button("URL laden") and url_in:
            data = process_meyton_url(url_in)
            save_shooting(username, data["date"], data["shooter"], data["discipline"], 
                         data["total_score"], ",".join(map(str, data["series"])), url_in, json.dumps(data.get("coordinates", [])))
            st.rerun()

# --- TAB 2: HISTORIE ---
with tabs[1]:
    st.header("Deine Ergebnisse")
    rows = get_all_shootings(username)
    if rows:
        df = pd.DataFrame(rows, columns=["ID", "User", "Datum", "Schütze", "Disziplin", "Gesamt", "Serien", "URL", "Coords", "Erstellt"])
        st.dataframe(df[["ID", "Datum", "Schütze", "Gesamt"]].sort_values("ID", ascending=False), use_container_width=True, hide_index=True)
        
        if st.button("Ausgewählte ID löschen"):
            # Logik für Lösch-ID hier (z.B. über ein st.number_input)
            pass
    else:
        st.info("Noch keine Einträge.")

# --- TAB 3: VERLAUF (OHNE UHRZEIT) ---
with tabs[2]:
    rows = get_all_shootings(username)
    if len(rows) > 1:
        import plotly.express as px
        df = pd.DataFrame(rows, columns=["ID", "User", "Datum", "Schütze", "Disziplin", "Gesamt", "Serien", "URL", "Coords", "Erstellt"])
        df["Datum"] = pd.to_datetime(df["Datum"]).dt.date # UHRZEIT WEG
        fig = px.line(df.sort_values("Datum"), x="Datum", y="Gesamt", markers=True)
        fig.update_xaxes(tickformat="%d.%m.%Y")
        st.plotly_chart(fig, use_container_width=True)

# --- TAB 4: DETAIL ---
with tabs[3]:
    rows = get_all_shootings(username)
    if rows:
        sel_id = st.selectbox("Training wählen", [r[0] for r in rows], format_func=lambda x: f"ID {x}")
        res = next(r for r in rows if r[0] == sel_id)
        
        c_plt, c_met = st.columns([2, 1])
        with c_plt:
            st.pyplot(create_target_plot(json.loads(res[8]) if res[8] else []))
        with c_met:
            st.metric("Gesamt", res[5])
            st.write(f"Datum: {res[2]}")
            st.write(f"Serien: {res[6]}")
