"""
app.py — F1 Porpoising Teaching Lab (Streamlit arayüzü)

Çalıştır:  streamlit run app.py
"""
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import streamlit as st
from matplotlib.patches import Circle, Polygon, FancyArrowPatch

import inspect
import re

import physics as ph
from lessons import DEFAULTS, LESSONS, PROFILE_LABELS

# streamlit sürümleri arası uyumluluk: width="stretch" (yeni) / use_container_width (eski)
STRETCH = ({"width": "stretch"} if "width" in inspect.signature(st.button).parameters
           else {"use_container_width": True})

# ---------------------------------------------------------------- sayfa ayarı
st.set_page_config(page_title="F1 Porpoising Teaching Lab", page_icon="🐬",
                   layout="wide", initial_sidebar_state="expanded")

# graphite / neon palet
BG = "#0d0f12"
PANEL = "#151920"
GRID = "#262c36"
TEXT = "#e6edf3"
MUTED = "#8b96a5"
CYAN = "#00e5ff"      # ön
MAGENTA = "#ff2bd6"   # arka
LIME = "#b6ff3c"      # ivme
AMBER = "#ffb300"     # eşik / lift
RED = "#ff3d5a"       # stall

CSS = f"""
<style>
:root {{ --bg:{BG}; --panel:{PANEL}; --grid:{GRID}; --cyan:{CYAN}; --mag:{MAGENTA};
         --lime:{LIME}; --amber:{AMBER}; --red:{RED}; --text:{TEXT}; --muted:{MUTED}; }}
.stApp {{ background: radial-gradient(1200px 600px at 80% -10%, #16202b 0%, {BG} 55%); color:{TEXT}; }}
[data-testid="stSidebar"] {{ background:#0a0c0f; border-right:1px solid {GRID}; }}
[data-testid="stHeader"] {{ background:transparent; }}
h1,h2,h3,h4 {{ letter-spacing:.02em; }}
.lab-title {{ font-size:2rem; font-weight:800; margin:0; line-height:1.1;
              background:linear-gradient(90deg,{CYAN},{MAGENTA}); -webkit-background-clip:text;
              -webkit-text-fill-color:transparent; }}
.lab-sub {{ color:{MUTED}; margin:.2rem 0 1rem 0; }}
.card {{ background:{PANEL}; border:1px solid {GRID}; border-radius:14px; padding:14px 18px; }}
.kpi {{ background:{PANEL}; border:1px solid {GRID}; border-radius:12px; padding:10px 14px; height:100%; }}
.kpi .l {{ color:{MUTED}; font-size:.72rem; text-transform:uppercase; letter-spacing:.08em; }}
.kpi .v {{ font-size:1.5rem; font-weight:700; font-variant-numeric:tabular-nums; }}
.kpi .u {{ color:{MUTED}; font-size:.8rem; font-weight:400; margin-left:4px; }}
.badge {{ display:inline-block; padding:3px 12px; border-radius:999px; font-weight:800;
          font-size:.95rem; letter-spacing:.06em; border:1px solid currentColor; }}
.b-ok {{ color:{LIME}; background:rgba(182,255,60,.08); }}
.b-forced {{ color:{AMBER}; background:rgba(255,179,0,.08); }}
.b-edge {{ color:#ff8a3d; background:rgba(255,138,61,.08); }}
.b-bad {{ color:{RED}; background:rgba(255,61,90,.10); animation:pulse 1.2s infinite; }}
@keyframes pulse {{ 0%,100% {{ box-shadow:0 0 0 0 rgba(255,61,90,.5); }} 50% {{ box-shadow:0 0 14px 2px rgba(255,61,90,.55); }} }}
.chip {{ display:inline-block; background:#1d232d; border:1px solid {GRID}; color:{TEXT};
         border-radius:8px; padding:2px 9px; margin:2px 4px 2px 0; font-size:.8rem;
         font-variant-numeric:tabular-nums; }}
.chip b {{ color:{CYAN}; }}
.stButton>button, .stFormSubmitButton>button {{
    background:linear-gradient(90deg,#00b8d4,#7c4dff); color:white; font-weight:700;
    border:0; border-radius:10px; }}
.stButton>button:hover, .stFormSubmitButton>button:hover {{ filter:brightness(1.15); color:white; }}
div[data-testid="stSlider"] label p {{ font-size:.86rem; }}
.stTabs [data-baseweb="tab"] {{ color:{MUTED}; }}
.stTabs [aria-selected="true"] {{ color:{CYAN}; }}
.watch li, .tryit li {{ margin-bottom:.25rem; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": PANEL, "savefig.facecolor": BG,
    "axes.edgecolor": GRID, "axes.labelcolor": TEXT, "xtick.color": MUTED, "ytick.color": MUTED,
    "text.color": TEXT, "grid.color": GRID, "grid.linewidth": 0.7, "axes.grid": True,
    "font.size": 9, "axes.titlesize": 10, "axes.titleweight": "bold", "legend.facecolor": PANEL,
    "legend.edgecolor": GRID, "legend.framealpha": 0.9,
})

# ---------------------------------------------------------------- durum
SLIDER_KEYS = list(DEFAULTS.keys())
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)
st.session_state.setdefault("mode", "Serbest Keşif")
st.session_state.setdefault("lesson_step", 0)
st.session_state.setdefault("exag", 8)


def load_lesson():
    """Seçili dersin parametre setini widget durumlarına yükle ve yeniden simüle ettir."""
    lesson = LESSONS[st.session_state["lesson_step"]]
    for k, v in {**DEFAULTS, **lesson["params"]}.items():
        st.session_state[k] = v
    st.session_state["_run"] = True


def on_mode_change():
    if st.session_state["mode"] == "Rehberli Ders":
        load_lesson()


def reset_defaults():
    for k, v in DEFAULTS.items():
        st.session_state[k] = v
    st.session_state["_run"] = True


# ---------------------------------------------------------------- kenar çubuğu
with st.sidebar:
    st.markdown("### 🐬 Porpoising Lab")
    st.radio("Mod", ["Serbest Keşif", "Rehberli Ders"], key="mode", horizontal=True,
             on_change=on_mode_change)
    st.divider()
    with st.form("params_form", border=False):
        st.markdown("**Parametreler**")
        st.slider("Seyir hızı [m/s]", 30.0, 100.0, step=1.0, key="V",
                  help="85 m/s ≈ 306 km/h")
        st.slider("Yol tümsek yüksekliği [mm]", 0.0, 30.0, step=0.5, key="bump_mm")
        st.slider("Süspansiyon sönüm çarpanı [×]", 0.3, 3.0, step=0.05, key="damp_mult")
        st.slider("Aerodinamik kuvvet çarpanı [×]", 0.5, 1.5, step=0.05, key="aero_mult")
        st.slider("Driver lift hedef hızı [m/s]", 30.0, 100.0, step=1.0, key="V_lift",
                  help="Seyir hızından BÜYÜK ya da eşitse lift uygulanmaz. "
                       "Küçükse sürücü belirlenen anda gazı keser ve hız bu değere düşer.")
        with st.expander("Gelişmiş"):
            st.selectbox("Yol profili", list(PROFILE_LABELS), key="profile",
                         format_func=PROFILE_LABELS.get)
            st.slider("Periyodik profil dalga boyu [m]", 5.0, 40.0, step=0.5, key="wavelength")
            st.slider("Lift başlangıcı [s]", 1.0, 7.0, step=0.5, key="t_lift")
        submitted = st.form_submit_button("⚡ Uygula ve yeniden simüle et", **STRETCH)
    st.button("↺ Varsayılanlara dön", on_click=reset_defaults, **STRETCH)
    st.caption("Kaydırıcıları ayarla, sonra **Uygula** düğmesine bas. "
               "Model didaktiktir; gerçek bir aracın kalibrasyonu değildir.")

# ---------------------------------------------------------------- simülasyon
def current_simparams() -> ph.SimParams:
    s = st.session_state
    return ph.SimParams(V=float(s["V"]), bump_mm=float(s["bump_mm"]), damp_mult=float(s["damp_mult"]),
                        aero_mult=float(s["aero_mult"]), V_lift=float(s["V_lift"]),
                        profile=s["profile"], wavelength=float(s["wavelength"]),
                        t_lift=float(s["t_lift"]))


@st.cache_data(show_spinner=False, max_entries=32)
def run_cached(sp_tuple):
    return ph.simulate(ph.SimParams(*sp_tuple))


def sp_to_tuple(sp: ph.SimParams):
    return (sp.V, sp.bump_mm, sp.damp_mult, sp.aero_mult, sp.V_lift, sp.profile,
            sp.bump_len, sp.bump_pos, sp.wavelength, sp.t_end, sp.t_lift, sp.decel, sp.fs)


if st.session_state["mode"] == "Rehberli Ders" and "res" not in st.session_state:
    load_lesson()

if submitted or st.session_state.pop("_run", False) or "res" not in st.session_state:
    try:
        with st.spinner("Simüle ediliyor…"):
            st.session_state["res"] = run_cached(sp_to_tuple(current_simparams()))
    except Exception as e:  # pragma: no cover
        st.error(f"Simülasyon başarısız: {e}")
        st.stop()

res = st.session_state["res"]
sp: ph.SimParams = res["sp"]
p: ph.VehicleParams = res["p"]
t = res["t"]
fs = sp.fs


# ---------------------------------------------------------------- çizim yardımcıları
def road_profile_xy(s_front, xs):
    """Araç çerçevesindeki x (CG'den, m) noktaları için yol yüksekliği [m]."""
    u, _ = ph.road_height(s_front - p.a + xs, sp)
    return u


# Gövde silueti: (CG'ye göre x, zemin çizgisinden yükseklik)
_BODY_X = np.array([-2.30, -2.15, -1.50, -0.60, 0.00, 0.45, 1.10, 1.90, 2.70, 3.30, 3.50])
_BODY_H = np.array([0.18, 0.55, 0.60, 0.82, 0.95, 0.78, 0.55, 0.40, 0.28, 0.16, 0.06])


def draw_car(ax, i, E):
    """Yandan şematik: gövde, tekerlekler, yol, downforce okları, clearance ölçüleri."""
    z, th = res["z"][i], res["theta"][i]
    s_front = res["s"][i]
    hf, hr = res["hf"][i], res["hr"][i]
    Lf, Lr = res["Lf"][i], res["Lr"][i]
    x0, x1 = -6.0, 7.0
    xs = np.linspace(x0, x1, 400)
    road = E * road_profile_xy(s_front, xs)

    # yol
    ax.fill_between(xs, road, -0.9, color="#1a1f27", zorder=1)
    ax.plot(xs, road, color="#4b5666", lw=2, zorder=2)
    world = s_front - p.a + xs
    for k in np.arange(np.ceil(world.min() / 4) * 4, world.max(), 4.0):
        xm = k - (s_front - p.a)
        ym = float(np.interp(xm, xs, road))
        ax.plot([xm, xm], [ym - 0.04, ym - 0.2], color="#3a4452", lw=2, zorder=2)

    # zemin çizgisi (datum'a göre, abartılı)
    def _h0(x):  # aero yokken zemin yüksekliği, lineer (x=-b → h0r, x=+a → h0f)
        return p.h0r + (p.h0f - p.h0r) * (x + p.b) / p.L

    def floor_y(x):
        return E * (_h0(x) + z + x * th)

    xb = np.linspace(-2.3, 3.5, 120)
    yb_floor = np.array([floor_y(x) for x in xb])
    h_prof = np.interp(xb, _BODY_X, _BODY_H)
    top = yb_floor + h_prof
    stalled = (hf < res["h_att_f"]) or (hr < res["h_att_r"])
    body_col = "#232a35"
    edge = RED if stalled else CYAN
    ax.add_patch(Polygon(np.c_[np.r_[xb, xb[::-1]], np.r_[top, yb_floor[::-1]]], closed=True,
                         fc=body_col, ec=edge, lw=1.6, zorder=5))
    ax.plot(xb, yb_floor, color=edge, lw=3.2, zorder=6, solid_capstyle="round")

    # kokpit / halo / arka kanat
    cx = 0.45
    ax.add_patch(Circle((cx - 0.05, floor_y(cx) + 0.97), 0.13, fc=AMBER, ec="none", zorder=7))
    xr = -2.28
    ax.plot([xr, xr + 0.05], [floor_y(xr) + 0.45, floor_y(xr) + 1.05], color=MAGENTA, lw=2.5, zorder=6)
    ax.plot([xr - 0.1, xr + 0.55], [floor_y(xr) + 1.05, floor_y(xr + 0.55) + 1.1], color=MAGENTA, lw=3, zorder=7)
    xf = 3.45
    ax.plot([xf - 0.35, xf + 0.1], [floor_y(xf) + 0.04, floor_y(xf) + 0.03], color=CYAN, lw=3, zorder=7)

    # tekerlekler (yolu takip eder)
    R = 0.36
    for xa, col in ((p.a, CYAN), (-p.b, MAGENTA)):
        yc = float(np.interp(xa, xs, road)) + R
        ax.add_patch(Circle((xa, yc), R, fc="#10141a", ec=col, lw=2, zorder=4))
        ax.add_patch(Circle((xa, yc), 0.13, fc=col, ec="none", alpha=.35, zorder=4))

    # downforce okları (uzunluk ∝ kuvvet)
    for xa, Lx, col in ((p.a, Lf, CYAN), (-p.b, Lr, MAGENTA)):
        top_y = floor_y(xa) + 1.9
        ln = 0.9 * Lx / 8000.0 + 0.1
        ax.add_patch(FancyArrowPatch((xa, top_y), (xa, top_y - ln), arrowstyle="-|>", mutation_scale=16,
                                     color=col, lw=2.5, zorder=8))
        ax.text(xa, top_y + 0.1, f"{Lx/1000:.1f} kN", color=col, ha="center", fontsize=9, fontweight="bold")

    # clearance ölçüleri
    for xa, hh, col, off in ((p.a + 0.55, hf, CYAN, p.a), (-p.b - 0.55, hr, MAGENTA, -p.b)):
        yr = float(np.interp(xa, xs, road))
        yfl = floor_y(xa)
        ax.annotate("", xy=(xa, yr), xytext=(xa, yfl),
                    arrowprops=dict(arrowstyle="<->", color=AMBER, lw=1.4), zorder=9)
        ax.text(xa + (0.12 if xa > 0 else -0.12), (yr + yfl) / 2, f"{hh*1e3:.1f} mm",
                color=AMBER, fontsize=9, fontweight="bold", va="center",
                ha="left" if xa > 0 else "right", zorder=9)

    ax.set_xlim(x0, x1)
    ax.set_ylim(-0.9, 3.1)
    ax.set_aspect("equal")
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    for sp_ in ax.spines.values():
        sp_.set_visible(False)
    ax.set_title(f"t = {t[i]:.2f} s   ·   V = {res['V'][i]:.0f} m/s ({res['V'][i]*3.6:.0f} km/h)"
                 f"   ·   dikey abartma ×{E}", loc="left", color=MUTED, fontsize=9)


def fig_car(i, E):
    fig, ax = plt.subplots(figsize=(11, 3.7))
    draw_car(ax, i, E)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.92, bottom=0.01)
    return fig


def lift_line(ax):
    if sp.V_lift < sp.V:
        ax.axvline(sp.t_lift, color=AMBER, ls=":", lw=1.5)
        ax.text(sp.t_lift, ax.get_ylim()[1], " driver lift", color=AMBER, fontsize=8, va="top")


def fig_clearance(tc):
    fig, ax = plt.subplots(figsize=(6.2, 3.4))
    ax.plot(t, res["hf"] * 1e3, color=CYAN, lw=1.6, label="Ön clearance")
    ax.plot(t, res["hr"] * 1e3, color=MAGENTA, lw=1.6, label="Arka clearance")
    ax.axhline(res["h_att_f"] * 1e3, color=CYAN, ls="--", lw=1.2, alpha=.8, label="Ön attachment-loss eşiği")
    ax.axhline(res["h_att_r"] * 1e3, color=MAGENTA, ls="--", lw=1.2, alpha=.8, label="Arka attachment-loss eşiği")
    lo = min(res["hf"].min(), 0.012) * 1e3
    ax.set_ylim(max(lo - 3, 0), max(res["hr"].max() * 1e3 + 4, 70) + 16)
    lift_line(ax)
    ax.axvline(tc, color=TEXT, lw=1, alpha=.7)
    ax.set_xlim(0, t[-1])
    ax.set_xlabel("zaman [s]")
    ax.set_ylabel("floor clearance [mm]")
    ax.set_title("Ön / arka floor clearance")
    ax.legend(loc="upper left", fontsize=7, ncol=2, borderpad=.3, labelspacing=.25)
    fig.tight_layout()
    return fig


def fig_accel(tc):
    g = 9.81
    a = res["az"] / g
    w = max(int(0.25 * fs), 3)
    env = np.array([np.abs(a[max(0, k - w):k + w]).max() for k in range(len(a))])
    fig, ax = plt.subplots(figsize=(6.2, 3.4))
    ax.fill_between(t, -env, env, color=LIME, alpha=.10, lw=0, label="Genlik zarfı")
    ax.plot(t, a, color=LIME, lw=1.1, label="CG dikey ivme")
    ax.axhline(0, color=GRID, lw=1)
    lift_line(ax)
    ax.axvline(tc, color=TEXT, lw=1, alpha=.7)
    lim = max(0.5, float(np.abs(a).max()) * 1.35)
    ax.set_ylim(-lim, lim)
    ax.set_xlim(0, t[-1])
    ax.set_xlabel("zaman [s]")
    ax.set_ylabel("a_z [g]")
    ax.set_title("CG dikey ivmesi")
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    fig.tight_layout()
    return fig


def fig_aero(i):
    hh = np.linspace(2e-3, 0.095, 400)
    V = res["V"][i]
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.2), sharey=False)
    for ax, key, col, name in ((axs[0], "f", CYAN, "Ön"), (axs[1], "r", MAGENTA, "Arka")):
        ClA = getattr(p, f"ClA_{key}")
        hpk, wlo, whi = (getattr(p, f"{n}_{key}") for n in ("hpk", "wlo", "whi"))
        Vref = sp.V
        curve = ph.downforce_static(hh, Vref, ClA, hpk, wlo, whi, p.baseline, sp.aero_mult)
        ax.plot(hh * 1e3, curve / 1e3, color=col, lw=2, label=f"{name} downforce @ {Vref:.0f} m/s")
        ax.axvline(ph.attachment_threshold(hpk, wlo) * 1e3, color=col, ls="--", lw=1, alpha=.8)
        ax.axvline(hpk * 1e3, color=GRID, ls=":", lw=1)
        h_t = res["h" + key]
        L_t = ph.downforce_static(h_t, res["V"], ClA, hpk, wlo, whi, p.baseline, sp.aero_mult)
        ax.plot(h_t * 1e3, L_t / 1e3, color=TEXT, lw=0.6, alpha=.35, label="yörünge")
        ax.scatter([res["h" + key + "0"] * 1e3],
                   [float(ph.downforce_static(res["h" + key + "0"], Vref, ClA, hpk, wlo, whi,
                                              p.baseline, sp.aero_mult)) / 1e3],
                   color=AMBER, s=50, zorder=5, label="denge noktası")
        ax.scatter([h_t[i] * 1e3], [L_t[i] / 1e3], color=RED, s=60, zorder=6, label="şimdi")
        ax.set_ylim(0, float(curve.max()) / 1e3 * 1.55)
        ax.text(hpk * 1e3, ax.get_ylim()[1] * 0.5, " tepe", color=MUTED, fontsize=8, rotation=90, va="center")
        ax.set_xlabel("ride height [mm]")
        ax.set_ylabel("downforce [kN]")
        ax.set_title(f"{name} aks — tepe + stall eğrisi (kesikli = attachment-loss)")
        ax.legend(fontsize=7, loc="upper right", ncol=2, borderpad=.3, labelspacing=.25)
    fig.tight_layout()
    return fig


def show(fig, placeholder=None):
    (placeholder or st).pyplot(fig, clear_figure=True)
    plt.close(fig)


# ---------------------------------------------------------------- başlık
st.markdown('<p class="lab-title">F1 Porpoising Teaching Lab</p>'
            '<p class="lab-sub">Ground-effect kaynaklı zıplamayı parametreleri değiştirerek keşfet — '
            'heave + pitch modeli, tepe + stall aero eğrisi.</p>', unsafe_allow_html=True)

def md_li(items):
    """Madde listesini HTML <li> olarak üret (**kalın** → <b>)."""
    return "".join("<li>" + re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", w) + "</li>" for w in items)


# ---------------------------------------------------------------- rehberli ders
if st.session_state["mode"] == "Rehberli Ders":
    labels = [f"{i+1} · {l['icon']} {l['title']}" for i, l in enumerate(LESSONS)]
    st.radio("Ders adımı", range(len(LESSONS)), key="lesson_step", horizontal=True,
             format_func=lambda i: labels[i], on_change=load_lesson, label_visibility="collapsed")
    L = LESSONS[st.session_state["lesson_step"]]
    st.markdown(f"#### {L['icon']} Adım {st.session_state['lesson_step']+1}: {L['title']} "
                f"<span style='color:{MUTED};font-weight:400;font-size:.95rem'>— {L['tagline']}</span>",
                unsafe_allow_html=True)
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown(L["body"])
    with c2:
        st.markdown("**👁 Gözlemle**")
        st.markdown(f"<ul class='watch'>{md_li(L['watch'])}</ul>", unsafe_allow_html=True)
        st.markdown("**🧪 Dene**")
        st.markdown(f"<ul class='tryit'>{md_li(L['try_'])}</ul>", unsafe_allow_html=True)
    P = {**DEFAULTS, **L["params"]}
    chips = (f"<span class='chip'>V <b>{P['V']:.0f}</b> m/s</span>"
             f"<span class='chip'>tümsek <b>{P['bump_mm']:.1f}</b> mm</span>"
             f"<span class='chip'>sönüm <b>×{P['damp_mult']:.2f}</b></span>"
             f"<span class='chip'>aero <b>×{P['aero_mult']:.2f}</b></span>"
             f"<span class='chip'>lift hedefi <b>{'yok' if P['V_lift'] >= P['V'] else str(int(P['V_lift'])) + ' m/s'}</b></span>"
             f"<span class='chip'>profil <b>{PROFILE_LABELS[P['profile']]}</b></span>")
    st.markdown("<div class='card'>Bu adımın hazır ayarları: " + chips + "</div>", unsafe_allow_html=True)
    st.button("↺ Bu adımın ayarlarını yeniden yükle", on_click=load_lesson)
    st.write("")

# ---------------------------------------------------------------- KPI
m = res["metrics"]
badge_cls = {"STABİL": "b-ok", "SÖNÜMLÜ": "b-ok", "ZORLANMIŞ TİTREŞİM": "b-forced",
             "SINIRDA": "b-edge", "PORPOISING": "b-bad"}[m["state"]]
k1, k2, k3, k4, k5 = st.columns([1.5, 1, 1, 1, 1])
k1.markdown(f"<div class='kpi'><div class='l'>Durum</div><div class='v'>"
            f"<span class='badge {badge_cls}'>{m['state']}</span></div>"
            f"<div class='u' style='margin:0'>{m['note']}</div></div>", unsafe_allow_html=True)
for col, lab, val, unit in ((k2, "Pik |a_z|", f"{m['peak_g']:.2f}", "g"),
                            (k3, "Arka clearance salınımı", f"{m['pp_rear_mm']:.1f}", "mm p-p"),
                            (k4, "Salınım frekansı", f"{m['freq_hz']:.1f}" if m["pp_rear_mm"] > 0.5 else "—", "Hz"),
                            (k5, "Stall'da geçen süre", f"{m['stall_frac']*100:.0f}", "%")):
    col.markdown(f"<div class='kpi'><div class='l'>{lab}</div><div class='v'>{val}"
                 f"<span class='u'>{unit}</span></div></div>", unsafe_allow_html=True)
st.caption(f"Dinlenme ride height @ {sp.V:.0f} m/s: ön **{res['hf0']*1e3:.1f} mm**, arka **{res['hr0']*1e3:.1f} mm** "
           f"· stall eşiği: ön {res['h_att_f']*1e3:.0f} mm, arka {res['h_att_r']*1e3:.0f} mm")

# ---------------------------------------------------------------- animasyon
st.markdown("##### 🏎️ Yandan şematik")
ctl1, ctl2, ctl3 = st.columns([4, 1.3, 1.2])
t_max = float(t[-1])
st.session_state["t_view"] = min(float(st.session_state.get("t_view", 0.0)), t_max)
with ctl1:
    t_view = st.slider("Zaman [s]", 0.0, t_max, step=0.02, key="t_view")
with ctl2:
    E = st.select_slider("Dikey abartma", options=[1, 2, 4, 8, 12, 16], key="exag")
with ctl3:
    st.write("")
    play = st.button("▶ Oynat", **STRETCH)

frame_ph = st.empty()
if play:
    for tt in np.arange(0.0, t_max, 0.08):
        show(fig_car(min(int(round(tt * fs)), len(t) - 1), E), frame_ph)
        time.sleep(0.02)
    show(fig_car(len(t) - 1, E), frame_ph)
else:
    i_view = min(int(round(t_view * fs)), len(t) - 1)
    show(fig_car(i_view, E), frame_ph)

# ---------------------------------------------------------------- grafikler
i_view = min(int(round(t_view * fs)), len(t) - 1)
gc1, gc2 = st.columns(2)
with gc1:
    show(fig_clearance(t[i_view]))
with gc2:
    show(fig_accel(t[i_view]))

with st.expander("🌀 Aero eğrisi: çalışma noktası ve yörünge",
                 expanded=(st.session_state["mode"] == "Rehberli Ders"
                           and st.session_state["lesson_step"] in (1, 3))):
    show(fig_aero(i_view))
    st.caption("Eğri, seçili seyir hızındaki downforce–ride height ilişkisidir. Tepenin sağında alçaldıkça "
               "downforce artar (yay etkisini zayıflatır); tepenin solunda akış ayrılır ve downforce çöker. "
               "Beyaz iz, simülasyon boyunca aracın bu eğri üzerinde gezdiği yoldur.")
