import streamlit as st
import pandas as pd
import json
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

# Eigene Module (Stelle sicher, dass die Dateien existieren)
from database import init_db, save_shooting, get_all_shootings, delete_shooting
from pdf_parser import process_meyton_url, process_pdf_bytes
from auth import init_auth

# --- KONFIGURATION ---
st.set_page_config(page_title="Meytapp - Schießen", page_icon="🎯", layout="wide")

# --- GRAFIK LOGIK (MATPLOTLIB) ---
def create_target_matplotlib(coordinates: list[dict]):
    """Erstellt eine ISSF-konforme Luftgewehrscheibe."""
    fig, ax = plt.subplots(figsize=(6, 6))
    
    # ISSF Radien für LG (in mm)
    rings = {
        1: 22.75, 2: 20.25, 3: 17.75, 4: 15.25, 
        5: 12.75, 6: 10.25, 7: 7.75, 8: 5.25, 9: 2.75
    }
    
    # 1. Scheibe zeichnen
    for r_num in range(1, 10):
        radius = rings[r_num]
        # Ring 4 bis 9 bilden den schwarzen Spiegel
        f_color = 'black' if r_num >= 4 else 'white'
        e_color = 'white' if r_num >= 4 else 'black'
        
        circle = plt.Circle((0, 0), radius, edgecolor=e_color, facecolor=f_color, zorder=1)
        ax.add_patch(circle)
        
        # Ringzahlen (auf der vertikalen Achse)
        t_color = 'white' if r_num >= 4 else 'black'
        ax.text(0, -radius + 0.5, str(r_num), color=t_color, ha='center', va='bottom', fontsize=7, zorder=2)

    # 2. Die 10 (Massiver weißer Punkt im Zentrum)
    ax.add_patch(plt.Circle((0, 0), 0.25, color='white', zorder=2))

    # 3. Schüsse einzeichnen
    if coordinates:
        for shot in coordinates:
            # Umrechnung von Hundertstel-mm in mm
            x = shot.get("x", 0) / 100.0
            y = shot.get("y", 0) / 100.0
            ring = shot.get("ring", 0)

            # Farb-Logik
            if ring >= 10.0:
                s_color = 'red'
            elif ring >= 9.0:
                s_color = 'yellow'
            else:
                s_color = 'black'
            
            # Randfarbe für bessere Sichtbarkeit auf Schwarz
            edge = 'white' if s_color == 'black' and abs(x) < 15 else 'black'
            
            ax.scatter(x, y, color=s_color, edgecolors=edge, s=70, alpha=0.9, zorder=4)

    ax.set_xlim(-25, 25)
    ax.set_ylim(-25, 25)
    ax.set_aspect('equal')
    ax.axis('off')
    plt.tight_layout()
    return fig

# --- AUTHENTIFIZIERUNG ---
init_db()
if "authenticator" not in st.session_state:
    st.session_state.authenticator = init_auth()

authenticator = st.session_state.authenticator

# Login-Check
authenticator.login(location="main")

if st.session_state.get("authentication_status") is False:
    st.error("Login fehlgeschlagen.")
    tab_reg = st.tabs(["Registrieren"])[0]
    with tab_reg:
        authenticator.register_user(location="main", merge_username_email=True)
    st.stop()

elif st.session_state.get("authentication_status") is None:
    tab_log, tab_reg = st.tabs(["Anmelden", "Registrieren"])
    with tab_reg:
        authenticator.register_user(location="main", merge_username_email=True)
    st.info("Bitte anmelden oder registrieren.")
    st.stop()

# --- HAUPTPROGRAMM (NUR WENN EINGELOGGT) ---
username = st.session_state.username
st.sidebar.title(f"🎯 Hallo, {st.session_state.name}")
authenticator.logout(location="sidebar")

tab_import, tab_history, tab_progress, tab_detail = st.tabs([
    "📥 Import", "📋 Historie", "📈 Verlauf", "🎯 Detail"
])

# 1. IMPORT
with tab_import:
    st.header("Ergebnisse hinzufügen")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Meyton URL")
        url_input = st.text_input("Link aus QR-Code einfügen")
        if st.button("URL laden", type="primary"):
            if url_input:
                data = process_meyton_url(url_input)
                if data["total_score"] > 0:
                    save_shooting(user_id=username, date=data["date"], shooter=data["shooter"],
                                  discipline=data["discipline"], total_score=data["total_score"],
                                  series=",".join(map(str, data["series"])), 
                                  url=url_input, coordinates=json.dumps(data.get("coordinates", [])))
                    st.success("Erfolg!")
                    st.rerun()

    with col2:
        st.subheader("PDF Upload")
        uploaded_pdf = st.file_uploader("Meyton PDF wählen", type=["pdf"])
        if uploaded_pdf:
            data = process_pdf_bytes(uploaded_pdf.read())
            save_shooting(user_id=username, date=data["date"], shooter=data["shooter"],
                          discipline=data["discipline"], total_score=data["total_score"],
                          series=",".join(map(str, data["series"])), 
                          url=None, coordinates=json.dumps(data.get("coordinates", [])))
            st.success("PDF importiert!")
            st.rerun()

# 2. HISTORIE
with tab_history:
    st.header("Deine Schießen")
    shootings = get_all_shootings(user_id=username)
    if shootings:
        df = pd.DataFrame(shootings, columns=["ID", "User", "Datum", "Schütze", "Disziplin", "Gesamt", "Serien", "URL", "Coords", "Erstellt"])
        st.dataframe(df[["ID", "Datum", "Schütze", "Gesamt", "Disziplin"]].sort_values("Datum", ascending=False), hide_index=True)
        
        del_id = st.number_input("Eintrag löschen (ID eingeben)", min_value=1, step=1)
        if st.button("Löschen"):
            delete_shooting(del_id, username)
            st.rerun()

# 3. VERLAUF
with tab_progress:
    st.header("Leistungskurve")
    shootings = get_all_shootings(user_id=username)
    if len(shootings) >= 2:
        import plotly.express as px
        df = pd.DataFrame(shootings, columns=["ID", "User", "Datum", "Schütze", "Disziplin", "Gesamt", "Serien", "URL", "Coords", "Erstellt"])
        df["Datum"] = pd.to_datetime(df["Datum"])
        fig = px.line(df.sort_values("Datum"), x="Datum", y="Gesamt", markers=True, color="Schütze")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nicht genug Daten für eine Grafik.")

# 4. DETAIL ANSICHT
with tab_detail:
    st.header("Analyse")
    shootings = get_all_shootings(user_id=username)
    if shootings:
        options = {s[0]: f"{s[2]} - {s[3]} ({s[5]} Ringe)" for s in shootings}
        selected_id = st.selectbox("Wähle ein Training/Wettkampf", options.keys(), format_func=lambda x: options[x])
        
        # Daten des gewählten Schießens holen
        res = next(s for s in shootings if s[0] == selected_id)
        coords = json.loads(res[8]) if res[8] else []
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.pyplot(create_target_matplotlib(coords))
        with c2:
            st.metric("Gesamtringe", res[5])
            st.write(f"**Disziplin:** {res[4]}")
            st.write(f"**Datum:** {res[2]}")
            
            st.subheader("Serien")
            try:
                shots = [float(x) for x in res[6].split(",")]
                for i in range(0, len(shots), 10):
                    s_vals = shots[i:i+10]
                    st.write(f"**S{i//10+1}:** {sum(s_vals):.1f}  \n  <small>{s_vals}</small>", unsafe_allow_html=True)
            except:
                st.write("Keine Seriendaten verfügbar.")
