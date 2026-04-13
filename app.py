import json
import math

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from pyzbar.pyzbar import decode

from auth import init_auth
from database import delete_shooting, get_all_shootings, init_db, save_shooting
from pdf_parser import process_pdf_bytes

# ---------------------------------------------------------------------------
# Initialisierung
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Meytapp🎯", layout="wide")
init_db()

if "authenticator" not in st.session_state:
    st.session_state.authenticator = init_auth()

auth = st.session_state.authenticator
auth.login(location="main")

# ---------------------------------------------------------------------------
# Auth-Gate
# ---------------------------------------------------------------------------

if st.session_state.get("authentication_status") is not True:
    t_login, t_reg = st.tabs(["Login", "Registrieren"])

    with t_login:
        if st.session_state.get("authentication_status") is False:
            st.error("Benutzername oder Passwort falsch. Bitte erneut versuchen.")
        else:
            st.info("Bitte anmelden oder im Tab 'Registrieren' ein Konto erstellen.")

    with t_reg:
        try:
            reg_result = auth.register_user(location="main", merge_username_email=True)
            if reg_result and isinstance(reg_result, tuple) and reg_result[0]:
                st.success(
                    f"Registrierung erfolgreich! Willkommen, {reg_result[2]}. "
                    "Du kannst dich jetzt im Tab 'Login' anmelden."
                )
        except Exception:
            pass

    st.stop()

# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def avg_per_shot(serien_str: str, gesamt: int) -> float:
    """Durchschnitt pro Schuss aus den gespeicherten Ringwerten."""
    if not serien_str:
        return float(gesamt)
    try:
        vals = [float(x.strip()) for x in serien_str.split(",") if x.strip()]
        if vals:
            return round(sum(vals) / len(vals), 2)
    except ValueError:
        pass
    return float(gesamt)


def recalc_shots(stored: list, discipline: str) -> list:
    """Berechnet x/y-Koordinaten aus gespeicherten Ring- und Winkelwerten."""
    if "Pistole" in discipline:
        ring_step, inner_radius = 8.0, 5.5
    else:
        ring_step, inner_radius = 2.5, 0.5

    shots = []
    for s in stored:
        ring = s["ring"]
        angle_clock = math.degrees(math.atan2(s["x"], s["y"])) % 360
        floor_r = math.floor(ring)
        frac = ring - floor_r
        outer = inner_radius + (10 - floor_r) * ring_step
        inner_r = (inner_radius + (10 - (floor_r + 1)) * ring_step) if floor_r < 10 else 0.0
        frac_safe = 0.05 + (frac / 0.9) * 0.90
        radius = outer - frac_safe * (outer - inner_r)
        theta = math.radians(angle_clock)
        shots.append({
            "ring": ring,
            "x": round(radius * math.sin(theta), 2),
            "y": round(radius * math.cos(theta), 2),
        })
    return shots


def render_target(shots: list, discipline: str = "Luftgewehr", zoom: float = 1.0):
    """Zeichnet die Schussscheibe mit matplotlib."""
    if "Pistole" in discipline:
        ring_step, inner_radius, spiegel_ab, full_limit = 8.0, 5.5, 7, 86
    else:
        ring_step, inner_radius, spiegel_ab, full_limit = 2.5, 0.5, 4, 26

    limit = full_limit / zoom
    radii = {n: inner_radius + (10 - n) * ring_step for n in range(1, 11)}

    fig, ax = plt.subplots(figsize=(5, 5))
    for ring_num in sorted(radii.keys()):
        val = radii[ring_num]
        is_black = spiegel_ab <= ring_num < 10
        ax.add_patch(plt.Circle(
            (0, 0), val,
            facecolor="black" if is_black else "white",
            edgecolor="white" if is_black else "black",
            linewidth=0.5,
            zorder=ring_num,
        ))

    for s in shots:
        ring = s["ring"]
        color = (
            "red" if ring >= 10.0
            else "yellow" if ring >= 9.0
            else "white" if ring >= spiegel_ab
            else "black"
        )
        ax.scatter(s["x"], s["y"], color=color, edgecolors="black",
                   s=55, linewidths=0.5, alpha=0.95, zorder=20)

    ax.set_xlim(-limit, limit)
    ax.set_ylim(-limit, limit)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor("#1a1a1a")
    ax.set_facecolor("#1a1a1a")
    return fig


def import_pdf(pdf_bytes: bytes) -> None:
    """Verarbeitet PDF-Bytes und speichert das Ergebnis in der Datenbank."""
    data = process_pdf_bytes(pdf_bytes)
    save_shooting(
        st.session_state.username,
        data["date"],
        data["shooter"],
        data["discipline"],
        data["total_score"],
        ",".join(map(str, data["series"])),
        None,
        json.dumps(data["coordinates"]),
    )
    st.toast(
        f"Import erfolgreich! {data['shooter']} – "
        f"{data['total_score']} Ringe ({len(data['coordinates'])} Schüsse)",
        icon="🎯",
    )


def scan_qr(image_bytes: bytes):
    """Dekodiert einen QR-Code aus Bild-Bytes. Gibt den Text zurück oder None."""
    file_bytes = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    decoded = decode(gray) or decode(cv2.GaussianBlur(gray, (5, 5), 0))
    return decoded[0].data.decode("utf-8") if decoded else None

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.sidebar.title(f"User: {st.session_state.name}")
auth.logout(location="sidebar")

# ---------------------------------------------------------------------------
# Hauptbereich
# ---------------------------------------------------------------------------

vorname = st.session_state.name.split()[0] if st.session_state.name else st.session_state.username
st.title(f"Gut Schuss, {vorname}!")

res = get_all_shootings(st.session_state.username)

t_imp, t_his, t_ver, t_det = st.tabs(["📥 Import", "📋 Historie", "📈 Verlauf", "🎯 Detail"])

# ---------------------------------------------------------------------------
# Tab: Import
# ---------------------------------------------------------------------------

with t_imp:
    st.subheader("📷 QR-Code scannen")
    cam = st.camera_input("QR-Code fotografieren")
    if cam:
        qr_text = scan_qr(cam.read())
        if qr_text:
            st.success(f"QR-Code erkannt: {qr_text}")
            with st.spinner("PDF wird heruntergeladen und importiert ..."):
                try:
                    response = requests.get(qr_text, timeout=15)
                    response.raise_for_status()
                    content = response.content
                    if not content.startswith(b"%PDF"):
                        st.error(
                            "Die URL liefert keine gültige PDF-Datei. "
                            "Möglicherweise ist eine Anmeldung im Meyton-System erforderlich."
                        )
                    else:
                        import_pdf(content)
                        st.rerun()
                except requests.RequestException as e:
                    st.error(f"PDF konnte nicht heruntergeladen werden: {e}")
                except Exception as e:
                    st.error(f"Fehler beim Importieren: {e}")
        else:
            st.error("Kein QR-Code erkannt – bitte näher heranhalten oder Licht verbessern.")

    st.divider()
    st.subheader("📄 PDF hochladen")
    up_pdf = st.file_uploader("Meyton PDF hochladen", type="pdf")
    if st.button("PDF importieren"):
        if not up_pdf:
            st.warning("Bitte zuerst eine PDF-Datei auswählen.")
        else:
            try:
                import_pdf(up_pdf.read())
                st.rerun()
            except Exception as e:
                st.error(f"Fehler beim Importieren der PDF: {e}")

# ---------------------------------------------------------------------------
# Tab: Historie
# ---------------------------------------------------------------------------

with t_his:
    if not res:
        st.info("Noch keine Ergebnisse. Importiere zuerst ein PDF.")
    else:
        df = pd.DataFrame(
            res, columns=["db_id", "User", "Datum", "Schütze", "Disp", "Gesamt", "Serien", "URL", "Coords", "Time"]
        )
        df = df.sort_values("db_id", ascending=False).reset_index(drop=True)
        df.insert(0, "Nr", range(1, len(df) + 1))

        st.dataframe(df[["Nr", "Datum", "Disp", "Gesamt"]], use_container_width=True, hide_index=True)

        sel_nr = st.selectbox(
            "Eintrag auswählen",
            df["Nr"].tolist(),
            format_func=lambda n: (
                f"#{n} – {df[df['Nr']==n]['Datum'].values[0]} – "
                f"{df[df['Nr']==n]['Gesamt'].values[0]} Ringe"
            ),
        )
        if st.button("Ausgewählten Eintrag löschen", type="secondary"):
            db_id = int(df[df["Nr"] == sel_nr]["db_id"].values[0])
            delete_shooting(db_id, st.session_state.username)
            st.toast("Eintrag erfolgreich gelöscht.", icon="🗑️")
            st.rerun()

# ---------------------------------------------------------------------------
# Tab: Verlauf
# ---------------------------------------------------------------------------

with t_ver:
    if not res:
        st.info("Noch keine Ergebnisse.")
    elif len(res) < 2:
        st.info("Mindestens 2 Ergebnisse für den Verlauf nötig.")
    else:
        df2 = pd.DataFrame(
            res, columns=["db_id", "User", "Datum", "Schütze", "Disp", "Gesamt", "Serien", "URL", "Coords", "Time"]
        )
        df2["Datum"] = pd.to_datetime(df2["Datum"], dayfirst=True).dt.date
        df2["Ø Ringe/Schuss"] = df2.apply(lambda r: avg_per_shot(r["Serien"], r["Gesamt"]), axis=1)

        fig = px.line(
            df2.sort_values("Datum"),
            x="Datum",
            y="Ø Ringe/Schuss",
            markers=True,
            title="Durchschnittliche Ringe pro Schuss",
        )
        fig.update_layout(yaxis=dict(range=[0, 11]), yaxis_title="Ø Ringe pro Schuss")
        st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Tab: Detail
# ---------------------------------------------------------------------------

with t_det:
    if not res:
        st.info("Noch keine Ergebnisse.")
    else:
        df3 = pd.DataFrame(
            res, columns=["db_id", "User", "Datum", "Schütze", "Disp", "Gesamt", "Serien", "URL", "Coords", "Time"]
        )
        df3 = df3.sort_values("db_id", ascending=False).reset_index(drop=True)
        df3.insert(0, "Nr", range(1, len(df3) + 1))

        choice_nr = st.selectbox(
            "Auswahl",
            df3["Nr"].tolist(),
            format_func=lambda n: (
                f"#{n} – {df3[df3['Nr']==n]['Datum'].values[0]} – "
                f"{df3[df3['Nr']==n]['Gesamt'].values[0]} Ringe"
            ),
        )
        row = df3[df3["Nr"] == choice_nr].iloc[0]
        discipline = row["Disp"]
        shots = recalc_shots(json.loads(row["Coords"]), discipline)

        zoom = st.slider("🔍 Zoom", min_value=1.0, max_value=8.0, value=1.0, step=0.5)

        col_scheibe, col_info = st.columns([2, 1])
        with col_scheibe:
            st.pyplot(render_target(shots, discipline, zoom=zoom))
        with col_info:
            st.metric("Gesamt", row["Gesamt"])
            st.metric("Ø pro Schuss", avg_per_shot(row["Serien"], row["Gesamt"]))
            st.write(f"Waffe: {discipline}")
            st.write(f"Serien: {row['Serien']}")
