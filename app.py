import streamlit as st
import pandas as pd
import json
import math
import matplotlib.pyplot as plt
from database import init_db, save_shooting, get_all_shootings, delete_shooting
from pdf_parser import process_pdf_bytes
from auth import init_auth

st.set_page_config(page_title="Meytapp🎯", layout="wide")
init_db()

if "authenticator" not in st.session_state:
    st.session_state.authenticator = init_auth()

auth = st.session_state.authenticator
auth.login(location="main")

if st.session_state.get("authentication_status") is not True:
    t1, t2 = st.tabs(["Login", "Registrieren"])
    with t2: auth.register_user(location="main", merge_username_email=True)
    st.stop()


def recalc_shots(stored, discipline):
    """Koordinaten immer frisch aus Ring + gespeichertem Winkel berechnen."""
    if "Pistole" in discipline:
        ring_step = 8.0
        inner_radius = 5.5
    else:
        ring_step = 2.5
        inner_radius = 0.5

    shots = []
    for s in stored:
        ring = s['ring']
        angle_clock = math.degrees(math.atan2(s['x'], s['y'])) % 360

        floor_r = math.floor(ring)
        frac = ring - floor_r
        outer = inner_radius + (10 - floor_r) * ring_step
        inner_r = (inner_radius + (10 - (floor_r + 1)) * ring_step) if floor_r < 10 else 0.0
        frac_safe = 0.05 + (frac / 0.9) * 0.90
        radius = outer - frac_safe * (outer - inner_r)

        theta = math.radians(angle_clock)
        shots.append({
            'ring': ring,
            'x': round(radius * math.sin(theta), 2),
            'y': round(radius * math.cos(theta), 2)
        })
    return shots


def render_target(shots, discipline="Luftgewehr", zoom=1.0):
    if "Pistole" in discipline:
        ring_step = 8.0
        inner_radius = 5.5
        spiegel_ab = 7
        full_limit = 86
    else:
        ring_step = 2.5
        inner_radius = 0.5
        spiegel_ab = 4
        full_limit = 26

    limit = full_limit / zoom
    radii = {n: inner_radius + (10 - n) * ring_step for n in range(1, 11)}

    fig, ax = plt.subplots(figsize=(5, 5))
    for ring_num in sorted(radii.keys()):
        val = radii[ring_num]
        is_black = spiegel_ab <= ring_num < 10
        ax.add_patch(plt.Circle((0, 0), val,
                                facecolor='black' if is_black else 'white',
                                edgecolor='white' if is_black else 'black',
                                linewidth=0.5, zorder=ring_num))

    for s in shots:
        x, y, ring = s['x'], s['y'], s['ring']
        c = 'red' if ring >= 10.0 else ('yellow' if ring >= 9.0 else ('white' if ring >= spiegel_ab else 'black'))
        ax.scatter(x, y, color=c, edgecolors='black', s=55, linewidths=0.5, alpha=0.95, zorder=20)

    ax.set_xlim(-limit, limit); ax.set_ylim(-limit, limit)
    ax.set_aspect('equal'); ax.axis('off')
    fig.patch.set_facecolor('#1a1a1a')
    ax.set_facecolor('#1a1a1a')
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
        st.toast(f"✅ Import erfolgreich! {data['shooter']} – {data['total_score']} Ringe ({len(data['coordinates'])} Schüsse)", icon="🎯")
        st.rerun()

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
        discipline = row[4]

        zoom = st.slider("🔍 Zoom", min_value=1.0, max_value=8.0, value=1.0, step=0.5)

        stored = json.loads(row[8])
        shots = recalc_shots(stored, discipline)

        c_p, c_i = st.columns([2, 1])
        with c_p:
            st.pyplot(render_target(shots, discipline, zoom=zoom))
        with c_i:
            st.metric("Gesamt", row[5])
            st.write(f"Waffe: {discipline}")
            st.write(f"Serien: {row[6]}")
