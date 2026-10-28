"""
lessons.py — Rehberli Ders içerikleri ve her adıma özel hazır parametre setleri.

`params` anahtarları, app.py kenar çubuğundaki widget anahtarlarıyla birebir aynıdır
(session_state üzerinden yüklenir).
"""

# Serbest keşif varsayılanı — 85 m/s'de bir tümsek porpoising başlatır.
DEFAULTS = dict(
    V=85.0,            # seyir hızı [m/s]
    bump_mm=8.0,       # tümsek yüksekliği [mm]
    damp_mult=1.0,     # süspansiyon sönüm çarpanı
    aero_mult=1.0,     # aero kuvvet çarpanı
    V_lift=100.0,      # driver lift hedef hızı [m/s] — seyir hızından büyükse lift yok
    profile="single",  # "none" | "single" | "periodic"
    wavelength=14.0,   # periyodik profil dalga boyu [m]
    t_lift=4.5,        # lift başlangıç zamanı [s]
)

PROFILE_LABELS = {
    "none": "Yok (düz yol)",
    "single": "Tek tümsek",
    "periodic": "Periyodik tümsekler",
}

LESSONS = [
    dict(
        title="Denge",
        icon="⚖️",
        tagline="Yaylar ve downforce nasıl dengeye gelir?",
        body=(
            "Araç dururken ya da yavaş giderken ride height'ı yalnızca **yay sertliği ve ağırlık** belirler. "
            "Hız arttıkça floor'un yarattığı downforce aracı yere bastırır; yaylar sıkışır ve "
            "**yay kuvveti = downforce** olduğu noktada yeni bir denge oluşur.\n\n"
            "Düşük hızda (40 m/s) aero kuvvet küçüktür: ride height neredeyse başlangıç değerinde kalır. "
            "Küçük bir tümsek sistemi dengeden çıkarır; **sönümleyici** enerjiyi çekip salınımı birkaç yarım periyotta bitirir."
        ),
        watch=[
            "Ön ve arka ride height çizgileri tümsekten sonra aynı dengeye geri dönüyor.",
            "CG ivmesi (yeşil) hızla sönüyor — salınım **büyümüyor**.",
            "Durum rozeti **SÖNÜMLÜ** (veya STABİL).",
        ],
        try_=[
            "Sönüm çarpanını 0.3'e indir: salınım daha uzun sürer ama yine de söner.",
            "Tümsek yüksekliğini 20 mm yap: tepki büyür ama karakter değişmez (doğrusal bölge).",
        ],
        params=dict(V=40.0, bump_mm=5.0, damp_mult=1.0, aero_mult=1.0, V_lift=100.0,
                    profile="single"),
    ),
    dict(
        title="Hava akışı etkisi",
        icon="🌬️",
        tagline="Downforce, ride height'a bağlıdır — tepe ve stall.",
        body=(
            "Floor'un altındaki hava akışı yere yaklaştıkça hızlanır, basınç düşer ve **downforce artar**. "
            "Ama belirli bir ride height'tan (**tepe**) sonra akış sıkışır, ayrılır ve downforce **aniden çöker** (stall). "
            "Eğrinin yüksek tarafında alçaldıkça downforce artar: bu bir *negatif sertlik* gibidir, yay etkisini azaltır. "
            "Stall tarafında ise eğim tersine döner ve akışın tepkisi **gecikmelidir** (τ ≈ 30 ms).\n\n"
            "Hızı 75 m/s'ye çıkarınca downforce ~V² ile büyür, ride height düşer ve araç **tepe noktasına yaklaşır**. "
            "Alttaki *Aero eğrisi* panelinde çalışma noktasını görebilirsin."
        ),
        watch=[
            "Dinlenme ride height'ı 40 m/s'ye göre belirgin biçimde düşük (ön ≈ 28 mm, arka ≈ 60 mm).",
            "Aero eğrisinde çalışma noktası, stall eşiğinin (kesikli çizgi) hemen üstünde.",
            "Hâlâ SÖNÜMLÜ: salınım ~2 s içinde bitiyor. Ama bu, kararlılık payının azaldığı bölgeye girdin.",
        ],
        try_=[
            "Aero çarpanını 1.15'e çıkar: çalışma noktası stall eşiğine iner ve **porpoising başlar** (salınım sönmez, ~0.45 g'de oturur).",
            "Aero çarpanını 0.8'e indir: araç tepeden uzaklaşır, tamamen sakinleşir.",
        ],
        params=dict(V=75.0, bump_mm=5.0, damp_mult=1.0, aero_mult=1.0, V_lift=100.0,
                    profile="single"),
    ),
    dict(
        title="Yol tümseği tahriki",
        icon="🛣️",
        tagline="Yol dalga boyu gövde rezonansıyla çakışırsa?",
        body=(
            "Periyodik tümsekler aracı **sürekli** zorlar. Tahrik frekansı `f = V / λ` (hız / dalga boyu) "
            "gövde heave doğal frekansına (~4–5 Hz) denk gelirse **rezonans** oluşur: küçük bir yol girdisi büyük bir salınıma dönüşür.\n\n"
            "Burada 60 m/s'de λ = 14 m → f ≈ 4.3 Hz, yani tam rezonans bölgesi. Salınımın nedeni **yolun tahriki**dir; "
            "porpoising'den farklı olarak tümsek bittiğinde (ya da hız değişince) kendiliğinden devam etmez."
        ),
        watch=[
            "CG ivmesi yol tahrikiyle senkron, sabit genlikli bir sinüs gibi.",
            "Durum rozeti **ZORLANMIŞ TİTREŞİM** — porpoising değil.",
            "Sönüm çarpanı sonucu büyük ölçüde değiştiriyor.",
        ],
        try_=[
            "Sönüm çarpanını 0.5 / 2.0 yap ve ivme genliğini karşılaştır.",
            "Gelişmiş ayarlardan dalga boyunu 8 m ya da 24 m yap: rezonanstan çıkınca genlik düşer.",
            "Hızı 40 m/s'ye düşür: tahrik frekansı ~3 Hz'e kayar, ivme genliği belirgin biçimde azalır.",
        ],
        params=dict(V=60.0, bump_mm=6.0, damp_mult=1.0, aero_mult=1.0, V_lift=100.0,
                    profile="periodic", wavelength=14.0),
    ),
    dict(
        title="Porpoising döngüsü",
        icon="🐬",
        tagline="Stall → kaldırma → yeniden tutunma → tekrar çökme.",
        body=(
            "Yüksek hızda araç, ride height'ı stall eşiğine çok yakın bir noktada dengelenir. Küçük bir tümsek "
            "arka ucu eşiğin altına iter: **akış ayrılır, downforce çöker**, yaylar aracı yukarı iter, ride height "
            "artınca **akış yeniden tutunur**, downforce geri gelir ve araç tekrar aşağı çekilir. "
            "Akışın gecikmesi (τ) bu döngüye enerji pompalar: **negatif sönüm** gibi çalışır.\n\n"
            "Sonuç: ~5 Hz'lik, genliği büyüyen ve sonra **limit çevrimine** oturan bir zıplama. "
            "Gerçek F1'de bu döngü sürücüyü ve zemini yorar; çözüm genelde **gaz kesmek (driver lift)** ya da aracı yükseltmektir.\n\n"
            "4,5 s'de sürücü 60 m/s hedefine doğru gazı keser: downforce V²'yle düşer, çalışma noktası stall'dan uzaklaşır ve salınım söner."
        ),
        watch=[
            "CG ivmesinin zarfı (soluk yeşil bant) ilk saniyelerde büyüyor, sonra ~±1.3 g'de doygunluğa ulaşıyor.",
            "Clearance grafiğinde eğriler kesikli stall eşiğinin altına inip çıkıyor.",
            "4,5 s'den sonra (turuncu dikey çizgi) salınım sönüyor.",
        ],
        try_=[
            "Lift hedefini 100 m/s yap (lift yok): salınım sonuna kadar sürer.",
            "Hızı 75 m/s'ye düşür: porpoising kayboluyor — kritik hız eşiği var.",
            "Sönüm çarpanını 1.5 → 2.0 yap: 85 m/s'de porpoising ~2.0'da kayboluyor — yeterli sönüm aero beslemeyi yenebilir.",
            "Tümsek yüksekliğini 0 yap: denge **kararsız** ama mükemmel dengede hiç tetik yok — gerçekte her zaman bir pürüz vardır.",
        ],
        params=dict(V=85.0, bump_mm=8.0, damp_mult=1.0, aero_mult=1.0, V_lift=60.0,
                    profile="single", t_lift=4.5),
    ),
]
