"""
physics.py — F1 Porpoising Teaching Lab için indirgenmiş dereceli araç modeli.

Model (didaktik, gerçek bir aracın kalibrasyonu DEĞİLDİR):
  * Rijit gövde: heave z (CG dikey yer değiştirmesi, yukarı +) ve pitch θ (burun yukarı +).
  * Ön / arka aks: yay + sönümleyici (lastik rijit kabul edilir, etkin aks yayı kullanılır),
    zemin (plank) temasında progresif "bump stop" kuvveti.
  * Yol girdisi: tümsek profili u(s); arka aks aynı profili dingil mesafesi kadar geç görür.
  * Aero: floor downforce, ride height h'ın fonksiyonu — "tepe + stall" eğrisi
    (iki yarı-gauss: yüksekte geniş, alçakta dar/keskin). Akış gecikmesi birinci
    derece filtre (τ) ile modellenir; stall bölgesinde bu gecikme negatif sönüm
    gibi davranır ve porpoising'i besler.

Durum vektörü: y = [z, θ, ż, θ̇, Lf, Lr]   (Lf, Lr: gecikmeli ön/arka downforce, N)

Ride height:   h_f = h0_f + z + a·θ − u_f ,   h_r = h0_r + z − b·θ − u_r   [m]
Hareket:       m z̈  = F_f + F_r − Lf − Lr
               Iy θ̈ = a (F_f − Lf) − b (F_r − Lr)
               τ L̇ = L_statik(h, V) − L
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
import numpy as np
from scipy.integrate import solve_ivp

RHO = 1.2  # kg/m³

# --------------------------------------------------------------------------
# Parametreler
# --------------------------------------------------------------------------


@dataclass
class VehicleParams:
    m: float = 800.0          # kütle [kg]
    Iy: float = 1100.0        # pitch atalet [kg m²]
    a: float = 1.96           # CG -> ön aks [m]
    b: float = 1.64           # CG -> arka aks [m]
    kf: float = 3.2e5         # ön aks etkin yay sertliği [N/m]
    kr: float = 2.8e5         # arka aks [N/m]
    cf: float = 4000.0        # ön sönüm (çarpan = 1) [N s/m]
    cr: float = 3600.0        # arka sönüm [N s/m]
    h0f: float = 0.040        # aero yokken ön ride height [m]
    h0r: float = 0.085        # aero yokken arka ride height [m]
    h_min: float = 0.004      # zemin (plank) temas eşiği [m]
    k_bs: float = 3.0e6       # bump stop sertliği [N/m]
    c_bs: float = 4000.0      # bump stop sönümü [N s/m]
    # aero (tepe + stall)
    ClA_f: float = 1.25       # ön CL·A tepe değeri [m²]
    ClA_r: float = 2.10       # arka (floor/difüzör ağırlıklı)
    baseline: float = 0.35    # tepenin oranı olarak "yükseklikten bağımsız" taban
    hpk_f: float = 0.030      # ön tepe ride height [m]
    hpk_r: float = 0.060      # arka tepe ride height [m]
    wlo_f: float = 0.0060     # alçak taraf (stall) genişliği [m] — dar = keskin
    wlo_r: float = 0.0085
    whi_f: float = 0.020      # yüksek taraf genişliği [m]
    whi_r: float = 0.030
    tau: float = 0.030        # aero akış gecikmesi [s]

    @property
    def L(self) -> float:
        return self.a + self.b


@dataclass
class SimParams:
    """Kullanıcının oynadığı parametreler."""
    V: float = 80.0            # seyir hızı [m/s]
    bump_mm: float = 8.0       # tümsek yüksekliği [mm]
    damp_mult: float = 1.0     # süspansiyon sönüm çarpanı
    aero_mult: float = 1.0     # aero kuvvet çarpanı
    V_lift: float = 80.0       # driver lift hedef hızı [m/s] (>= V ise lift yok)
    # gelişmiş
    profile: str = "single"    # "none" | "single" | "periodic"
    bump_len: float = 3.0      # tek tümsek uzunluğu [m]
    bump_pos: float = 60.0     # tek tümsek konumu [m]
    wavelength: float = 18.0   # periyodik profil dalga boyu [m]
    t_end: float = 8.0         # [s]
    t_lift: float = 4.5        # lift başlangıcı [s]
    decel: float = 15.0        # lift yavaşlaması [m/s²]
    fs: float = 500.0          # çıktı örnekleme [Hz]


# --------------------------------------------------------------------------
# Aero eğrisi: tepe + stall
# --------------------------------------------------------------------------


def aero_shape(h, hpk, wlo, whi, baseline):
    """Normalize CL(h)/CL_max: tepe noktası 1.0.

    h > hpk : geniş gauss ile 'baseline' tabanına doğru yavaş düşüş (yükseklik kaybı)
    h < hpk : dar gauss ile keskin düşüş (floor stall) — baseline altına da iner
    """
    h = np.asarray(h, dtype=float)
    hi = baseline + (1.0 - baseline) * np.exp(-0.5 * ((h - hpk) / whi) ** 2)
    lo = np.exp(-0.5 * ((h - hpk) / wlo) ** 2)
    return np.where(h >= hpk, hi, lo)


def downforce_static(h, V, ClA, hpk, wlo, whi, baseline, mult):
    return 0.5 * RHO * V**2 * ClA * mult * aero_shape(h, hpk, wlo, whi, baseline)


def attachment_threshold(hpk, wlo):
    """Stall başlangıcı: alçak taraf gauss'unun dönüm noktası (en dik düşüş)."""
    return hpk - wlo


# --------------------------------------------------------------------------
# Yol ve hız profili
# --------------------------------------------------------------------------


def speed_profile(t, sp: SimParams):
    """V(t) ve alınan yol s(t) (analitik)."""
    t = np.asarray(t, dtype=float)
    V0 = sp.V
    if sp.V_lift >= V0:
        return np.full_like(t, V0), V0 * t
    Vt = sp.V_lift
    t_ramp = (V0 - Vt) / sp.decel
    tl = sp.t_lift
    dt = np.clip(t - tl, 0.0, None)
    V = np.where(t < tl, V0, np.where(t < tl + t_ramp, V0 - sp.decel * dt, Vt))
    # s(t)
    s_lift = V0 * tl
    s_ramp = V0 * np.minimum(dt, t_ramp) - 0.5 * sp.decel * np.minimum(dt, t_ramp) ** 2
    s_after = Vt * np.clip(dt - t_ramp, 0.0, None)
    s = np.where(t < tl, V0 * t, s_lift + s_ramp + s_after)
    return V, s


def road_height(s, sp: SimParams):
    """Yol yüksekliği u(s) [m] ve eğimi du/ds."""
    s = np.asarray(s, dtype=float)
    H = sp.bump_mm * 1e-3
    if sp.profile == "none" or H == 0.0:
        return np.zeros_like(s), np.zeros_like(s)
    if sp.profile == "single":
        x = (s - sp.bump_pos) / sp.bump_len
        inside = (x >= 0) & (x <= 1)
        u = np.where(inside, 0.5 * H * (1 - np.cos(2 * np.pi * x)), 0.0)
        du = np.where(inside, 0.5 * H * 2 * np.pi * np.sin(2 * np.pi * x) / sp.bump_len, 0.0)
        return u, du
    # periyodik (washboard): λ boyunca yumuşak giriş
    lam = sp.wavelength
    s0 = sp.bump_pos
    x = s - s0
    ramp = np.clip(x / lam, 0.0, 1.0)
    dramp = np.where((x > 0) & (x < lam), 1.0 / lam, 0.0)
    w = 2 * np.pi / lam
    u = np.where(x > 0, H * ramp * np.sin(w * x), 0.0)
    du = np.where(x > 0, H * (dramp * np.sin(w * x) + ramp * w * np.cos(w * x)), 0.0)
    return u, du


# --------------------------------------------------------------------------
# Denge
# --------------------------------------------------------------------------


def _axle_contact(h, p: VehicleParams, hdot=0.0):
    pen = p.h_min - h
    return np.where(pen > 0, p.k_bs * pen - p.c_bs * hdot * (pen > 0), 0.0)


def static_ride_height(V, axle: str, p: VehicleParams, mult: float):
    """Verilen hızda düz yolda ön/arka ride height dengesi (yüksekten aşağı ilk kök)."""
    if axle == "f":
        k, h0, ClA, hpk, wlo, whi = p.kf, p.h0f, p.ClA_f, p.hpk_f, p.wlo_f, p.whi_f
    else:
        k, h0, ClA, hpk, wlo, whi = p.kr, p.h0r, p.ClA_r, p.hpk_r, p.wlo_r, p.whi_r

    def f(h):
        return k * (h0 - h) + float(_axle_contact(h, p)) - float(
            downforce_static(h, V, ClA, hpk, wlo, whi, p.baseline, mult))

    hs = np.linspace(h0, 0.0005, 800)
    fv = np.array([f(h) for h in hs])
    for i in range(len(hs) - 1):
        if fv[i] == 0.0:
            return float(hs[i])
        if fv[i] * fv[i + 1] < 0:
            lo, hi = hs[i + 1], hs[i]
            for _ in range(60):
                mid = 0.5 * (lo + hi)
                if f(lo) * f(mid) <= 0:
                    hi = mid
                else:
                    lo = mid
            return 0.5 * (lo + hi)
    return float(hs[-1])


# --------------------------------------------------------------------------
# ODE
# --------------------------------------------------------------------------


def _rhs_factory(p: VehicleParams, sp: SimParams):
    cf = p.cf * sp.damp_mult
    cr = p.cr * sp.damp_mult
    mult = sp.aero_mult
    L = p.L

    def parts(t, y):
        z, th, vz, wth, Lf, Lr = y
        V, s = speed_profile(t, sp)
        V = float(V)
        s = float(s)
        uf, duf = road_height(s, sp)
        ur, dur = road_height(s - L, sp)
        uf, ur = float(uf), float(ur)
        uf_dot, ur_dot = float(duf) * V, float(dur) * V
        zf, zr = z + p.a * th, z - p.b * th
        zfd, zrd = vz + p.a * wth, vz - p.b * wth
        hf = p.h0f + zf - uf
        hr = p.h0r + zr - ur
        hfd, hrd = zfd - uf_dot, zrd - ur_dot
        Ff = -p.kf * (zf - uf) - cf * hfd + float(_axle_contact(hf, p, hfd))
        Fr = -p.kr * (zr - ur) - cr * hrd + float(_axle_contact(hr, p, hrd))
        Lf_s = float(downforce_static(hf, V, p.ClA_f, p.hpk_f, p.wlo_f, p.whi_f, p.baseline, mult))
        Lr_s = float(downforce_static(hr, V, p.ClA_r, p.hpk_r, p.wlo_r, p.whi_r, p.baseline, mult))
        az = (Ff + Fr - Lf - Lr) / p.m
        alpha = (p.a * (Ff - Lf) - p.b * (Fr - Lr)) / p.Iy
        dLf = (Lf_s - Lf) / p.tau
        dLr = (Lr_s - Lr) / p.tau
        return np.array([vz, wth, az, alpha, dLf, dLr]), dict(
            hf=hf, hr=hr, V=V, s=s, uf=uf, ur=ur, Lf_s=Lf_s, Lr_s=Lr_s, az=az)

    def rhs(t, y):
        return parts(t, y)[0]

    return rhs, parts


def simulate(sp: SimParams | None = None, p: VehicleParams | None = None) -> dict:
    """Tek bir simülasyonu çalıştırır, sonuç sözlüğü döndürür (numpy dizileri)."""
    sp = sp or SimParams()
    p = p or VehicleParams()
    rhs, parts = _rhs_factory(p, sp)

    # denge başlangıç koşulu (t=0 hızı = V, düz yol)
    hf0 = static_ride_height(sp.V, "f", p, sp.aero_mult)
    hr0 = static_ride_height(sp.V, "r", p, sp.aero_mult)
    zf0, zr0 = hf0 - p.h0f, hr0 - p.h0r
    th0 = (zf0 - zr0) / p.L
    z0 = (p.b * zf0 + p.a * zr0) / p.L
    Lf0 = float(downforce_static(hf0, sp.V, p.ClA_f, p.hpk_f, p.wlo_f, p.whi_f, p.baseline, sp.aero_mult))
    Lr0 = float(downforce_static(hr0, sp.V, p.ClA_r, p.hpk_r, p.wlo_r, p.whi_r, p.baseline, sp.aero_mult))
    y0 = np.array([z0, th0, 0.0, 0.0, Lf0, Lr0])

    t_eval = np.arange(0.0, sp.t_end, 1.0 / sp.fs)
    sol = solve_ivp(rhs, (0.0, sp.t_end), y0, t_eval=t_eval, method="LSODA",
                    rtol=1e-6, atol=1e-9, max_step=0.002)
    if not sol.success:
        raise RuntimeError(f"ODE çözülemedi: {sol.message}")

    t = sol.t
    Y = sol.y
    keys = ["hf", "hr", "V", "s", "uf", "ur", "Lf_s", "Lr_s", "az"]
    out = {k: np.empty(len(t)) for k in keys}
    for i in range(len(t)):
        _, d = parts(t[i], Y[:, i])
        for k in keys:
            out[k][i] = d[k]

    res = dict(
        t=t, z=Y[0], theta=Y[1], vz=Y[2], wtheta=Y[3], Lf=Y[4], Lr=Y[5],
        hf=out["hf"], hr=out["hr"], V=out["V"], s=out["s"],
        u_f=out["uf"], u_r=out["ur"], az=out["az"],
        hf0=hf0, hr0=hr0,
        h_att_f=attachment_threshold(p.hpk_f, p.wlo_f),
        h_att_r=attachment_threshold(p.hpk_r, p.wlo_r),
        sp=sp, p=p,
    )
    res["metrics"] = analyze(res)
    return res


# --------------------------------------------------------------------------
# Analiz
# --------------------------------------------------------------------------


def analyze(res: dict) -> dict:
    """Salınım karakterini sayısal olarak özetler (arayüzdeki durum rozeti için)."""
    t, hr, hf, az = res["t"], res["hr"], res["hf"], res["az"]
    sp: SimParams = res["sp"]
    g = 9.81
    # yol girdisinden sonraki pencere (ilk tümsekten sonra) — lift öncesi
    t_cut = sp.t_lift if sp.V_lift < sp.V else sp.t_end
    t_start = 0.0
    if sp.profile != "none" and sp.bump_mm > 0:
        t_start = float(np.interp(sp.bump_pos, res["s"], t)) if res["s"][-1] > sp.bump_pos else 0.0
    m_all = (t >= t_start) & (t <= t_cut)
    # CG ivmesi içinde yüksek frekanslı kontak/gürültüyü ele: zarf = hareketli pencere pik
    amp = np.abs(az) / g

    def window_peak(t0, t1):
        m = (t >= t0) & (t < t1)
        return float(amp[m].max()) if m.any() else 0.0

    span = max(t_cut - t_start, 1e-6)
    q = span / 4.0
    early = window_peak(t_start, t_start + q)
    late = window_peak(t_cut - q, t_cut)
    peak = float(amp[m_all].max()) if m_all.any() else 0.0

    # ride height salınım genliği (tepeden tepeye, son çeyrek)
    m_late = (t >= t_cut - q) & (t <= t_cut)
    pp_r = float((hr[m_late].max() - hr[m_late].min()) * 1e3) if m_late.any() else 0.0
    pp_f = float((hf[m_late].max() - hf[m_late].min()) * 1e3) if m_late.any() else 0.0

    # baskın frekans (son çeyrek, arka ride height)
    freq = 0.0
    if m_late.sum() > 50:
        x = hr[m_late] - hr[m_late].mean()
        X = np.abs(np.fft.rfft(x * np.hanning(len(x))))
        fr = np.fft.rfftfreq(len(x), 1.0 / sp.fs)
        X[fr < 1.0] = 0
        freq = float(fr[np.argmax(X)]) if X.max() > 0 else 0.0

    # stall süresi oranı
    stalled = ((hr < res["h_att_r"]) | (hf < res["h_att_f"]))[m_all]
    stall_frac = float(stalled.mean()) if stalled.any() else 0.0

    # sınıflandırma
    forced = sp.profile == "periodic"
    if peak < 0.15 and pp_r < 1.0:
        state = "STABİL"
        note = "Salınım yok / ihmal edilebilir."
    elif pp_r < 2.0 and late <= early * 1.05 + 0.02:
        state = "SÖNÜMLÜ"
        note = "Tümsek tepkisi veriyor ama salınım sönüyor."
    elif forced and late <= max(early * 1.3, 0.3):
        state = "ZORLANMIŞ TİTREŞİM"
        note = "Salınım yolun tahriki ile sürülüyor."
    elif late > early * 1.05 + 0.05 or pp_r >= 4.0:
        state = "PORPOISING"
        note = "Salınım büyüyor / sürdürülüyor (limit çevrimi)."
    else:
        state = "SINIRDA"
        note = "Kararlılık sınırına yakın."
    return dict(state=state, note=note, peak_g=peak, early_g=early, late_g=late,
                pp_front_mm=pp_f, pp_rear_mm=pp_r, freq_hz=freq, stall_frac=stall_frac)


if __name__ == "__main__":
    import time
    for V in (40, 60, 70, 80, 90):
        t0 = time.time()
        r = simulate(SimParams(V=V, V_lift=V))
        m = r["metrics"]
        print(f"V={V:3d}  h_f0={r['hf0']*1e3:5.1f}  h_r0={r['hr0']*1e3:5.1f} mm | "
              f"{m['state']:<10s} peak={m['peak_g']:.2f}g early={m['early_g']:.2f} late={m['late_g']:.2f} "
              f"pp_r={m['pp_rear_mm']:.1f}mm f={m['freq_hz']:.1f}Hz stall={m['stall_frac']:.2f} ({time.time()-t0:.1f}s)")
