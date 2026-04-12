import streamlit as st
import pandas as pd
import json
import matplotlib.pyplot as plt
from database import init_db, save_shooting, get_all_shootings, delete_shooting
from pdf_parser import process_pdf_bytes
from auth import init_auth

st.set_page_config(page_title="Meytapp Pro 🎯", layout="wide")
init_db()

if "authenticator" not in st.session_state:
    st.session_state.authenticator = init_auth()

auth = st.session_state.authenticator
auth.login(location="main")

if st.session_state.get("authentication_status") is not True:
    t1, t2 = st.tabs(["Login", "Registrieren"])
    with t2: auth.register_user(location="main", merge_username_email=True)
    st.stop()

# --- GRAFIK FUNKTION ---
def render_target(shots, discipline="Luftgewehr"):
    fig, ax = plt.subplots(figsize=(5, 5))
    
    # Maßstäbe wählen
    if "Pistole" in discipline:
        radii = {1:77.75, 2:69.75, 3:61.75, 4:53.75, 5:45.75, 6:37.75, 7:29.75, 8:21.75, 9:13.75}
        spiegel_ab = 7
        limit = 80
    else:
        radii = {1:22.75, 2:20.25, 3:17.75, 4:15.25, 5:12.75, 6:10.25, 7:7.75, 8:5.25, 9:2.75}
        spiegel_ab = 4
        limit = 25
    
    for r, val in radii.items():
        is_spiegel = r >= spiegel_ab
        ax.add_patch(plt.Circle((0,0), val, facecolor='black' if is_spiegel else 'white', 
                                edgecolor='white' if is_spiegel else 'black', zorder=1))
    
    ax.add_patch(plt.Circle((0,0), 0.25 if "Gewehr" in discipline else 5.75, color='white', zorder=2))

    for s in shots:
        x, y, ring = s['x'], s['y'], s['ring']
        c = 'red' if ring >= 10.0 else ('yellow' if ring >= 9.0 else 'black')
        edge = 'white' if c == 'black' and abs(x) < (radii[spiegel_ab]) else 'black'
        ax.scatter(x, y, color=c, edgecolors=edge, s=50, alpha=0.9, zorder=5)

    ax.set_xlim(-limit, limit); ax.set_ylim(-limit, limit); ax.set_aspect('equal'); ax.axis('off')
    return fig

# --- UI ---
st.sidebar.title(f"User: {st.session_state.name}")
auth.logout(location="sidebar")

t_imp, t_his, t_ver, t_det = st.tabs(["📥 Import", "📋 Historie", "📈 Verlauf", "🎯 Detail"])

with t_imp:
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.write("### QR Scan")
        cam = st.camera_input("Scanner", label_visibility="collapsed")
    
    st.divider()
    
    up_pdf = st.file_uploader("Meyton PDF hochladen", type="pdf")
    if st.button("PDF importieren") and up_pdf:
        data = process_pdf_bytes(up_pdf.read())
        save_shooting(st.session_state.username, data["date"], data["shooter"], data["discipline"], 
                      data["total_score"], ",".join(map(str, data["series"])), None, json.dumps(data["coordinates"]))
        st.success(f"Erfolg! {len(data['coordinates'])} Schüsse gefunden."); st.rerun()

with t_his:
    res = get_all_shootings(st.session_state.username)
    if res:
        df = pd.DataFrame(res, columns=["ID", "User", "Datum", "Schütze", "Disp", "Gesamt", "Serien", "URL", "Coords", "Time"])
        st.dataframe(df[["ID", "Datum", "Disp", "Gesamt"]].sort_values("ID", ascending=False), use_container_width=True, hide_index=True)
        
        del_id = st.number_input("ID zum Löschen", min_value=0, step=1)
        if st.button("Löschen"):
            delete_shooting(del_id, st.session_state.username); st.rerun()

with t_ver:
    if res:
        df = pd.DataFrame(res, columns=["ID", "User", "Datum", "Schütze", "Disp", "Gesamt", "Serien", "URL", "Coords", "Time"])
        df["Datum"] = pd.to_datetime(df["Datum"], dayfirst=True).dt.date
        import plotly.express as px
        st.plotly_chart(px.line(df.sort_values("Datum"), x="Datum", y="Gesamt", markers=True), use_container_width=True)

with t_det:
    if res:
        choice = st.selectbox("Auswahl", [r[0] for r in res], format_func=lambda x: f"ID {x}")
        row = next(r for r in res if r[0] == choice)
        c_p, c_i = st.columns([2, 1])
        with c_p: st.pyplot(render_target(json.loads(row[8]), row[4]))
        with c_i: st.metric("Gesamt", row[5]); st.write(f"Waffe: {row[4]}"); st.write(f"Serien: {row[6]}")
