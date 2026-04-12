import streamlit as st
import pandas as pd
import json
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from datetime import datetime

from database import init_db, save_shooting, get_all_shootings, delete_shooting
from pdf_parser import process_meyton_url
from auth import init_auth

# --- NEUE MATPLOTLIB FUNKTION ---
def create_target_matplotlib(coordinates: list[dict]):
    """Erstellt eine physikalisch korrekte LG-Scheibe mit Matplotlib."""
    fig, ax = plt.subplots(figsize=(6, 6))
    
    # ISSF Radien für Luftgewehr (in mm)
    # Ring 1 ist außen (22.75mm), Ring 9 ist innen (2.75mm)
    # Die 10 ist ein Punkt mit Radius 0.25mm
    rings = {
        1: 22.75, 2: 20.25, 3: 17.75, 4: 15.25, 
        5: 12.75, 6: 10.25, 7: 7.75, 8: 5.25, 9: 2.75
    }
    
    # 1. Hintergrund und Spiegel (Ring 4 bis 9 sind schwarz)
    for r_num in range(1, 10):
        radius = rings[r_num]
        # Spiegel ab Ring 4 schwarz füllen
        facecolor = 'black' if r_num >= 4 else 'white'
        edgecolor = 'white' if r_num >= 4 else 'black'
        
        circle = plt.Circle((0, 0), radius, edgecolor=edgecolor, facecolor=facecolor, zorder=1)
        ax.add_patch(circle)
        
        # Ringzahlen beschriften
        text_color = 'white' if r_num >= 4 else 'black'
        ax.text(0, -radius + 0.5, str(r_num), color=text_color, ha='center', va='bottom', fontsize=8, zorder=2)

    # 2. Die 10 (Zentraler weißer Punkt)
    center_dot = plt.Circle((0, 0), 0.25, color='white', zorder=2)
    ax.add_patch(center_dot)

    # 3. Schüsse einzeichnen
    for shot in coordinates:
        # Meyton Koordinaten von Hundertstel-mm in mm umrechnen
        x = shot.get("x", 0) / 100.0
        y = shot.get("y", 0) / 100.0
        ring = shot.get("ring", 0)

        # Farbcodierung
        if ring >= 10.0:
            shot_color = 'red'
        elif ring >= 9.0:
            shot_color = 'yellow'
        else:
            shot_color = 'black'
            # Falls der Schuss im schwarzen Bereich liegt, geben wir ihm einen weißen Rand
            if abs(x) < 15.25 and abs(y) < 15.25:
                ax.scatter(x, y, color='black', edgecolors='white', s=50, alpha=0.8, zorder=4)
                continue

        ax.scatter(x, y, color=shot_color, edgecolors='black', s=60, alpha=0.8, zorder=4)

    # Layout-Einstellungen
    limit = 25  # mm
    ax.set_xlim(-limit, limit)
    ax.set_ylim(-limit, limit)
    ax.set_aspect('equal')
    ax.axis('off')
    fig.patch.set_facecolor('white')
    plt.tight_layout()
    
    return fig

# --- HILFSFUNKTIONEN ---
def scan_qr_code(img, debug: bool = False):
    import cv2
    from pyzbar.pyzbar import decode
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    clahe_img = clahe.apply(gray)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    processed_images = [gray, blurred, clahe.apply(blurred)]
    for processed in processed_images:
        decoded = decode(processed)
        for symbol in decoded:
            data = symbol.data.decode("utf-8")
            if data: return data, None
    return None, blurred if debug else None

def parse_series_string(series_str: str) -> dict[int, list]:
    if not series_str: return {}
    try:
        shots = [float(x.strip()) for x in series_str.split(",")]
        return {i//10 + 1: shots[i:i+10] for i in range(0, len(shots), 10)}
    except: return {}

def import_result(url: str, user_id: str):
    with st.spinner("PDF wird verarbeitet..."):
        try:
            data = process_meyton_url(url)
            if data["shooter"] and data["total_score"] > 0:
                series_str = ",".join(str(s) for s in data["series"])
                coords_str = json.dumps(data.get("coordinates", []))
                save_shooting(user_id=user_id, date=data["date"], shooter=data["shooter"],
                              discipline=data["discipline"], total_score=data["total_score"],
                              series=series_str, url=url, coordinates=coords_str)
                st.success(f"Ergebnis für {data['shooter']} gespeichert!")
                st.balloons()
                return True
        except Exception as e:
            st.error(f"Fehler: {str(e)}")
    return False

# --- APP START ---
st.set_page_config(page_title="Meytapp", page_icon="🎯", layout="wide")
init_db()
if "authenticator" not in st.session_state:
    st.session_state.authenticator = init_auth()

authenticator = st.session_state.authenticator
authenticator.login(location="main")

if st.session_state.get("authentication_status") is True:
    username = st.session_state.username
    st.sidebar.title(f"Hallo, {st.session_state.name}")
    authenticator.logout(location="sidebar")

    tab_import, tab_history, tab_progress, tab_detail = st.tabs(["📥 Import", "📋 Historie", "📈 Verlauf", "🎯 Detail"])

    # --- TAB IMPORT ---
    with tab_import:
        st.header("Ergebnis hinzufügen")
        url_input = st.text_input("Meyton URL")
        if st.button("URL Importieren"):
            if url_input: import_result(url_input, username)
        
        st.divider()
        uploaded_pdf = st.file_uploader("Oder PDF hochladen", type=["pdf"])
        if uploaded_pdf:
            from pdf_parser import process_pdf_bytes
            data = process_pdf_bytes(uploaded_pdf.read())
            save_shooting(user_id=username, date=data["date"], shooter=data["shooter"],
                          discipline=data["discipline"], total_score=data["total_score"],
                          series=",".join(str(s) for s in data["series"]), 
                          url=None, coordinates=json.dumps(data.get("coordinates", [])))
            st.success("PDF erfolgreich importiert!")

    # --- TAB HISTORIE ---
    with tab_history:
        shootings = get_all_shootings(user_id=username)
        if shootings:
            df = pd.DataFrame(shootings, columns=["ID", "User", "Datum", "Schütze", "Disziplin", "Gesamt", "Serien", "URL", "Coords", "Erstellt"])
            st.dataframe(df[["ID", "Datum", "Schütze", "Gesamt", "Disziplin"]], hide_index=True)
            del_id = st.number_input("ID zum Löschen", min_value=1, step=1)
            if st.button("Eintrag löschen"):
                delete_shooting(del_id, username)
                st.rerun()

    # --- TAB VERLAUF ---
    with tab_progress:
        shootings = get_all_shootings(user_id=username)
        if len(shootings) >= 2:
            import plotly.express as px
            df = pd.DataFrame(shootings, columns=["ID", "User", "Datum", "Schütze", "Disziplin", "Gesamt", "Serien", "URL", "Coords", "Erstellt"])
            df["Datum"] = pd.to_datetime(df["Datum"])
            fig = px.line(df.sort_values("Datum"), x="Datum", y="Gesamt", markers=True, title="Leistungskurve")
            st.plotly_chart(fig, use_container_width=True)

    # --- TAB DETAIL ---
    with tab_detail:
        shootings = get_all_shootings(user_id=username)
        if shootings:
            options = {s[0]: f"{s[2]} - {s[3]} ({s[5]} Ringe)" for s in shootings}
            selected_id = st.selectbox("Ergebnis wählen", options.keys(), format_func=lambda x: options[x])
            
            res = next(s for s in shootings if s[0] == selected_id)
            coords = json.loads(res[8]) if res[8] else []
            
            col1, col2 = st.columns([2, 1])
            with col1:
                if coords:
                    st.pyplot(create_target_matplotlib(coords))
                else:
                    st.info("Keine Grafikdaten verfügbar.")
            with col2:
                st.metric("Gesamt", f"{res[5]} Ringe")
                st.write(f"**Schütze:** {res[3]}")
                st.write(f"**Datum:** {res[2]}")
                st.write(f"**Disziplin:** {res[4]}")
                
                st.markdown("### Serien")
                s_dict = parse_series_string(res[6])
                for s_num, s_val in s_dict.items():
                    st.write(f"**S{s_num}:** {sum(s_val):.1f} ({', '.join(map(str, s_val))})")

elif st.session_state.get("authentication_status") is False:
    st.error("Login fehlgeschlagen.")
