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
st.set_page_config(page_title="Meytapp Pro", layout="wide")

# --- MATHEMATIK: RING & GRAD -> MM ---
def get_mm_coords(ring, grad):
    """
    Berechnet X/Y in Millimetern basierend auf der PDF-Info.
    Radius r = (10.9 - Ringwert) * 2.5mm (LG Standard)
    """
    # Radius in mm
    r = (10.9 - float(ring)) * 2.5
    # Winkel in Radiant (Meyton 0° = oben/12 Uhr)
    phi = math.radians(float(grad))
    
    x = r * math.sin(phi)
    y = r * math.cos(phi)
    return x, y

# --- GRAFIK: MATPLOTLIB (Maßstab in mm) ---
def create_target_plot(shots_data: list):
    fig, ax = plt.subplots(figsize=(5, 5))
    
    # ISSF Radien für LG in mm (Ring 1 bis 9)
    radii = {1: 22.75, 2: 20.25, 3: 17.75, 4: 15.25, 5: 12.75, 6: 10.25, 7: 7.75, 8: 5.25, 9: 2.75}
    
    for r_num, r_val in radii.items():
        color = 'black' if r_num >= 4 else 'white'
        edge = 'white' if r_num >= 4 else 'black'
        ax.add_patch(plt.Circle((0, 0), r_val, facecolor=color, edgecolor=edge, zorder=1))
        
        # Ringzahlen
        txt_c = 'white' if r_num >= 4 else 'black'
        ax.text(0, r_val - 1.2, str(r_num), color=txt_c, ha='center', fontsize=7, zorder=2)

    # Die 10 (Zentrumspunkt)
    ax.add_patch(plt.Circle((0, 0), 0.25, color='white', zorder=3))

    # Schüsse einzeichnen
    if shots_data:
        for s in shots_data:
            # Wir nehmen an, dass in der DB bereits die mm-Werte liegen
            x, y = s.get("x", 0), s.get("y", 0)
            ring = s.get("ring", 0)
            
            shot_color = 'red' if ring >= 10.0 else ('yellow' if ring >= 9.0 else 'black')
            shot_edge = 'white' if shot_color == 'black' and abs(x) < 15 else 'black'
            
            ax.scatter(x, y, color=shot_color, edgecolors=shot_edge, s=60, alpha=0.9, zorder=5)

    ax.set_xlim(-25, 25)
    ax.set_ylim(-25, 25)
    ax.set_aspect('equal')
    ax.axis('off')
    return fig

# --- AUTH & DB ---
init_db()
if "authenticator" not in st.session_state:
    st.session_state.authenticator = init_auth()

auth = st.session_state.authenticator
auth.login(location="main")

if st.session_state.get("authentication_status") is not True:
    t1, t2 = st.tabs(["Login", "Registrieren"])
    with t2: auth.register_user(location="main", merge_username_email=True)
    st.stop()

# --- APP LAYOUT ---
st.sidebar.title(f"User: {st.session_state.name}")
auth.logout(location="sidebar")

tab_import, tab_history, tab_stats, tab_detail = st.tabs(["📥 Import", "📋 Historie", "📈 Verlauf", "🎯 Detail"])

# 1. IMPORT (QR Preview kleiner)
with tab_import:
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.write("### QR Scanner")
        cam_file = st.camera_input("QR-Code scannen", label_visibility="collapsed")
    
    st.divider()
    
    c_pdf, c_url = st.columns(2)
    with c_pdf:
        st.write("### PDF Upload")
        pdf_file = st.file_uploader("Meyton PDF wählen", type="pdf")
        if st.button("PDF Auswerten") and pdf_file:
            # Hier muss dein pdf_parser die Funktion get_mm_coords nutzen!
            data = process_pdf_bytes(pdf_file.read())
            save_shooting(st.session_state.username, data["date"], data["shooter"], 
                          data["discipline"], data["total_score"], 
                          ",".join(map(str, data["series"])), None, json.dumps(data["coordinates"]))
            st.success("Importiert!")
            st.rerun()

# 2. HISTORIE (Vollständig)
with tab_history:
    st.write("### Deine Schießen")
    shootings = get_all_shootings(st.session_state.username)
    if shootings:
        df = pd.DataFrame(shootings, columns=["ID", "User", "Datum", "Schütze", "Disziplin", "Gesamt", "Serien", "URL", "Coords", "Time"])
        st.dataframe(df[["ID", "Datum", "Schütze", "Gesamt", "Disziplin"]].sort_values("ID", ascending=False), use_container_width=True, hide_index=True)
        
        del_id = st.number_input("ID zum Löschen", min_value=0, step=1)
        if st.button("Eintrag entfernen"):
            delete_shooting(del_id, st.session_state.username)
            st.rerun()

# 3. VERLAUF (Keine Uhrzeit)
with tab_stats:
    if shootings:
        df = pd.DataFrame(shootings, columns=["ID", "User", "Datum", "Schütze", "Disziplin", "Gesamt", "Serien", "URL", "Coords", "Time"])
        df["Datum"] = pd.to_datetime(df["Datum"]).dt.date # NUR DATUM
        import plotly.express as px
        fig = px.line(df.sort_values("Datum"), x="Datum", y="Gesamt", markers=True, title="Leistungskurve")
        fig.update_xaxes(tickformat="%d.%m.%Y")
        st.plotly_chart(fig, use_container_width=True)

# 4. DETAIL
with tab_detail:
    if shootings:
        options = {s[0]: f"{s[2]} - {s[5]} Ringe" for s in shootings}
        selection = st.selectbox("Training wählen", options.keys(), format_func=lambda x: options[x])
        res = next(s for s in shootings if s[0] == selection)
        
        col_plot, col_info = st.columns([2, 1])
        with col_plot:
            st.pyplot(create_target_plot(json.loads(res[8])))
        with col_info:
            st.metric("Gesamt", res[5])
            st.write(f"**Datum:** {res[2]}")
            st.write(f"**Serien:** {res[6]}")
