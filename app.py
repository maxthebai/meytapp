import streamlit as st
import pandas as pd
import json
import matplotlib.pyplot as plt
import numpy as np
from database import init_db, save_shooting, get_all_shootings, delete_shooting
from pdf_parser import process_pdf_bytes
from auth import init_auth

# --- SETUP ---
st.set_page_config(page_title="Meytapp Pro", layout="wide")
init_db()

if "authenticator" not in st.session_state:
    st.session_state.authenticator = init_auth()

auth = st.session_state.authenticator
auth.login(location="main")

if st.session_state.get("authentication_status") is not True:
    t1, t2 = st.tabs(["Login", "Registrieren"])
    with t2: auth.register_user(location="main", merge_username_email=True)
    st.stop()

# --- GRAFIK (EXAKT MM) ---
def render_target(shots):
    fig, ax = plt.subplots(figsize=(5, 5))
    # ISSF LG Radien (mm)
    radii = {1:22.75, 2:20.25, 3:17.75, 4:15.25, 5:12.75, 6:10.25, 7:7.75, 8:5.25, 9:2.75}
    
    for r, val in radii.items():
        is_spiegel = r >= 4
        ax.add_patch(plt.Circle((0,0), val, facecolor='black' if is_spiegel else 'white', 
                                edgecolor='white' if is_spiegel else 'black', zorder=1))
        ax.text(0, val-1.2, str(r), color='white' if is_spiegel else 'black', ha='center', fontsize=6, zorder=2)

    ax.add_patch(plt.Circle((0,0), 0.25, color='white', zorder=3)) # Die 10

    for s in shots:
        x, y, ring = s['x'], s['y'], s['ring']
        c = 'red' if ring >= 10.0 else ('yellow' if ring >= 9.0 else 'black')
        edge = 'white' if c == 'black' and abs(x) < 15 else 'black'
        ax.scatter(x, y, color=c, edgecolors=edge, s=50, alpha=0.9, zorder=5)

    ax.set_xlim(-25, 25); ax.set_ylim(-25, 25); ax.set_aspect('equal'); ax.axis('off')
    return fig

# --- UI ---
st.sidebar.title(f"Hallo {st.session_state.name}!")
auth.logout(location="sidebar")

t_imp, t_his, t_ver, t_det = st.tabs(["📥 Import", "📋 Historie", "📈 Verlauf", "🎯 Detail"])

# 1. IMPORT
with t_imp:
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.write("### QR Scan")
        cam = st.camera_input("Scanner", label_visibility="collapsed")
    
    st.divider()
    
    up_pdf = st.file_uploader("Meyton PDF hochladen", type="pdf")
    if st.button("PDF Auswerten") and up_pdf:
        data = process_pdf_bytes(up_pdf.read())
        save_shooting(st.session_state.username, data["date"], data["shooter"], "Luftgewehr", 
                      data["total_score"], ",".join(map(str, data["series"])), None, json.dumps(data["coordinates"]))
        st.success("Import abgeschlossen!"); st.rerun()

# 2. HISTORIE
with t_his:
    res = get_all_shootings(st.session_state.username)
    if res:
        df = pd.DataFrame(res, columns=["ID", "User", "Datum", "Schütze", "Disp", "Gesamt", "Serien", "URL", "Coords", "Time"])
        st.dataframe(df[["ID", "Datum", "Schütze", "Gesamt"]].sort_values("ID", ascending=False), use_container_width=True, hide_index=True)
        
        del_id = st.number_input("ID zum Löschen", min_value=0, step=1)
        if st.button("Eintrag löschen"):
            delete_shooting(del_id, st.session_state.username)
            st.rerun()

# 3. VERLAUF
with t_ver:
    if res:
        df = pd.DataFrame(res, columns=["ID", "User", "Datum", "Schütze", "Disp", "Gesamt", "Serien", "URL", "Coords", "Time"])
        df["Datum"] = pd.to_datetime(df["Datum"], dayfirst=True).dt.date
        import plotly.express as px
        fig = px.line(df.sort_values("Datum"), x="Datum", y="Gesamt", markers=True)
        fig.update_xaxes(tickformat="%d.%m.%Y")
        st.plotly_chart(fig, use_container_width=True)

# 4. DETAIL
with t_det:
    if res:
        choice = st.selectbox("Training wählen", [r[0] for r in res], format_func=lambda x: f"ID {x}")
        row = next(r for r in res if r[0] == choice)
        
        col_p, col_i = st.columns([2, 1])
        with col_p:
            st.pyplot(render_target(json.loads(row[8])))
        with col_i:
            st.metric("Ergebnis", row[5])
            st.write(f"**Datum:** {row[2]}")
            st.write(f"**Serien:** {row[6]}")
