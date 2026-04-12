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

# --- GRAFIK FUNKTION (MATPLOTLIB) ---
def create_target_plot(coordinates: list[dict]):
    """Erstellt eine maßstabsgetreue LG-Scheibe."""
    fig, ax = plt.subplots(figsize=(6, 6))
    
    # ISSF Radien für Luftgewehr (in mm)
    # Ring 1 (außen) bis Ring 9 (innen)
    ring_radii = {1: 22.75, 2: 20.25, 3: 17.75, 4: 15.25, 
                  5: 12.75, 6: 10.25, 7: 7.75, 8: 5.25, 9: 2.75}
    
    # 1. Ringe zeichnen
    for r, radius in sorted(ring_radii.items()):
        # Spiegel ab Ring 4 ist schwarz
        f_color = 'black' if r >= 4 else 'white'
        e_color = 'white' if r >= 4 else 'black'
        
        circle = plt.Circle((0, 0), radius, edgecolor=e_color, facecolor=f_color, zorder=1)
        ax.add_patch(circle)
        
        # Beschriftung
        t_color = 'white' if r >= 4 else 'black'
        ax.text(0, -radius + 0.3, str(r), color=t_color, ha='center', va='bottom', fontsize=8, zorder=2)

    # 2. Die Zehn (Zentraler weißer Punkt)
    ax.add_patch(plt.Circle((0, 0), 0.25, color='white', zorder=2))

    # 3. Treffer zeichnen
    if coordinates:
        for shot in coordinates:
            # Umrechnung von Hundertstel-mm in mm
            x = shot.get("x", 0) / 100.0
            y = shot.get("y", 0) / 100.0
            ring = shot.get("ring", 0)

            # Farbcode: 10er=Rot, 9er=Gelb, Rest=Schwarz
            if ring >= 10.0:
                c = 'red'
            elif ring >= 9.0:
                c = 'yellow'
            else:
                c = 'black'
            
            # Kontrastring für schwarze Treffer auf schwarzem Grund
            edge = 'white' if c == 'black' and abs(x) < 15 else 'black'
            ax.scatter(x, y, color=c, edgecolors=edge, s=80, alpha=0.85, zorder=5, linewidth=0.8)

    ax.set_xlim(-25, 25)
    ax.set_ylim(-25, 25)
    ax.set_aspect('equal')
    ax.axis('off')
    plt.tight_layout()
    return fig

# --- QR SCANNER LOGIK ---
def scan_qr_from_image(img):
    from pyzbar.pyzbar import decode
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    decoded = decode(gray)
    for obj in decoded:
        return obj.data.decode("utf-8")
    return None

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

# --- APP LAYOUT (Eingeloggt) ---
username = st.session_state.username
st.sidebar.title(f"🎯 {st.session_state.name}")
auth.logout(location="sidebar")

tabs = st.tabs(["📥 Import", "📋 Historie", "📈 Verlauf", "🎯 Detail"])

# --- TAB 1: IMPORT ---
with tabs[0]:
    st.header("Ergebnis importieren")
    
    m1, m2, m3 = st.tabs(["📷 Kamera / Scan", "🔗 URL", "📄 PDF Upload"])
    
    with m1:
        img_file = st.camera_input("QR-Code fotografieren")
        if img_file:
            file_bytes = np.frombuffer(img_file.read(), np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            qr_data = scan_qr_from_image(img)
            if qr_data:
                st.success(f"Gefunden: {qr_data}")
                if st.button("Diesen Link verarbeiten"):
                    data = process_meyton_url(qr_data)
                    save_shooting(username, data["date"], data["shooter"], data["discipline"], 
                                 data["total_score"], ",".join(map(str, data["series"])), qr_data, json.dumps(data.get("coordinates", [])))
                    st.rerun()
            else:
                st.warning("Kein QR-Code erkannt. Bitte näher ran oder URL manuell eingeben.")

    with m2:
        url_text = st.text_input("Meyton Link hier einfügen")
        if st.button("URL importieren"):
            data = process_meyton_url(url_text)
            save_shooting(username, data["date"], data["shooter"], data["discipline"], 
                         data["total_score"], ",".join(map(str, data["series"])), url_text, json.dumps(data.get("coordinates", [])))
            st.rerun()

    with m3:
        pdf_file = st.file_uploader("PDF Datei wählen", type="pdf")
        if pdf_file:
            data = process_pdf_bytes(pdf_file.read())
            save_shooting(username, data["date"], data["shooter"], data["discipline"], 
                         data["total_score"], ",".join(map(str, data["series"])), None, json.dumps(data.get("coordinates", [])))
            st.success("PDF erfolgreich importiert!")

# --- TAB 2: HISTORIE ---
with tabs[1]:
    data_list = get_all_shootings(username)
    if data_list:
        df = pd.DataFrame(data_list, columns=["ID", "User", "Datum", "Schütze", "Disziplin", "Gesamt", "Serien", "URL", "Coords", "Erstellt"])
        st.dataframe(df[["ID", "Datum", "Schütze", "Gesamt", "Disziplin"]].sort_values("ID", ascending=False), use_container_width=True, hide_index=True)
        
        del_id = st.number_input("ID zum Löschen", min_value=1, step=1)
        if st.button("Löschen"):
            delete_shooting(del_id, username)
            st.rerun()
    else:
        st.info("Noch keine Daten vorhanden.")

# --- TAB 3: VERLAUF ---
with tabs[2]:
    data_list = get_all_shootings(username)
    if len(data_list) > 1:
        import plotly.express as px
        df = pd.DataFrame(data_list, columns=["ID", "User", "Datum", "Schütze", "Disziplin", "Gesamt", "Serien", "URL", "Coords", "Erstellt"])
        df["Datum"] = pd.to_datetime(df["Datum"])
        fig = px.line(df.sort_values("Datum"), x="Datum", y="Gesamt", markers=True, color="Schütze", title="Leistungsentwicklung")
        st.plotly_chart(fig, use_container_width=True)

# --- TAB 4: DETAIL ---
with tabs[3]:
    data_list = get_all_shootings(username)
    if data_list:
        options = {s[0]: f"{s[2]} - {s[3]} ({s[5]} Ringe)" for s in data_list}
        sel = st.selectbox("Ergebnis wählen", options.keys(), format_func=lambda x: options[x])
        
        row = next(s for s in data_list if s[0] == sel)
        coords = json.loads(row[8]) if row[8] else []
        
        col_fig, col_info = st.columns([2, 1])
        with col_fig:
            st.pyplot(create_target_plot(coords))
        with col_info:
            st.metric("Gesamt", f"{row[5]} Ringe")
            st.write(f"**Disziplin:** {row[4]}")
            st.write(f"**Datum:** {row[2]}")
            st.subheader("Serien")
            try:
                s_list = [float(x) for x in row[6].split(",")]
                for i in range(0, len(s_list), 10):
                    chunk = s_list[i:i+10]
                    st.write(f"Serie {i//10+1}: **{sum(chunk):.1f}**")
                    st.caption(f"{chunk}")
            except:
                st.write("Keine Seriendaten.")
