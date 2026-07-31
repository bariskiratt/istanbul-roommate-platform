/**
 * Arayüz metinleri. Türkçe kaynak dildir; İngilizce sözlükte eksik bir anahtar
 * olursa Türkçe'ye düşülür (bkz. i18n/index.tsx).
 *
 * Anahtar düzeni: <alan>.<metin>  — ör. "nav.explore", "swipe.emptyTitle".
 */

const tr = {
  // ---- ortak ----
  "common.save": "Kaydet",
  "common.cancel": "İptal",
  "common.back": "Geri",
  "common.close": "Kapat",
  "common.delete": "Sil",
  "common.edit": "Düzenle",
  "common.loading": "Yükleniyor…",
  "common.retry": "Tekrar dene",
  "common.continue": "Devam Et",
  "common.perMonth": "/ay",
  "common.roomShare": "/ay oda payı",
  "common.currency": "₺",
  "common.houseListing": "Ev İlanı",
  "common.personalListing": "Kişisel İlan",
  "common.error": "Bir şeyler ters gitti.",

  // ---- alt menü / başlık ----
  "nav.discover": "Keşfet",
  "nav.likes": "Beğeniler",
  "nav.houses": "Evler",
  "nav.map": "Harita",
  "nav.messages": "Mesajlar",
  "nav.profile": "Profil",
  "nav.theme": "Tema",
  "nav.language": "Dil",
  "nav.themeLight": "Açık tema",
  "nav.themeDark": "Koyu tema",

  // ---- açılış sayfası ----
  "landing.findHouse": "Ev Bul",
  "landing.findRoommate": "Ev Arkadaşı Bul",
  "landing.budgetMap": "Bütçe Haritası",
  "landing.safety": "Güvenlik",
  "landing.howItWorks": "Nasıl Çalışır?",
  "landing.logout": "Çıkış Yap",
  "landing.login": "Giriş Yap",
  "landing.getStarted": "Hemen Başla",
  "landing.heroLine1": "Doğru ev arkadaşı,",
  "landing.heroFair": "adil",
  "landing.heroLine2": "bir kirayla.",
  "landing.heroSub":
    "İstanbul'daki üniversite öğrencileri için eşleşme platformu. Makine öğrenmesi destekli kira danışmanı, mahalle bütçe haritası ve doğrulanmış öğrenci topluluğu.",
  "landing.ctaContinue": "Keşfetmeye Devam Et",
  "landing.ctaFree": "Ücretsiz Başla",
  "landing.ctaBrowse": "İlanlara Göz At",
  "landing.statListings": "aktif ilan",
  "landing.statNeighborhoods": "mahalle haritada",
  "landing.statError": "medyan model hatası",
  "landing.statErrorValue": "%15,1",
  "landing.eduBadge": "Sadece .edu.tr uzantılı üniversite e-postasıyla kayıt",
  "landing.featuredTitle": "Öne çıkan evler",
  "landing.featuredSub": "Oda payı fiyatlarıyla",
  "landing.stepsEyebrow": "3 adımda ev arkadaşı bul",
  "landing.stepsTitle": "Bu kadar basit.",
  "landing.step1Title": "Profilini oluştur",
  "landing.step1Desc":
    "Üniversite e-postanla kayıt ol. Bütçeni, yaşam tarzını ve tercih ettiğin semtleri belirt.",
  "landing.step2Title": "Keşfet ve kaydır",
  "landing.step2Desc":
    "Gerçek ilanları gör, beğendiklerine sağa kaydır. Adil fiyat danışmanı kiraların piyasaya uygunluğunu söyler.",
  "landing.step3Title": "Eşleş ve tanış",
  "landing.step3Desc":
    "Karşılıklı beğeni eşleşme yaratır. Uygulama içi mesajlaşmayla güvenle iletişime geç.",
  "landing.signupFree": "Ücretsiz Kaydol",
  "landing.signupNote": "Kredi kartı gerekmez · Tamamen ücretsiz · .edu.tr gerekli",
  "landing.districtsTitle": "İstanbul'da ev ara",
  "landing.districtsSub": "En çok ilan olan semtler ve medyan oda payları",
  "landing.districtCount": "{count} ilan",
  "landing.districtMedian": "~{price} ₺/ay oda",
  "landing.why1Title": "Adil fiyat danışmanı",
  "landing.why1Desc":
    "LightGBM modeli, istenen kiranın piyasaya uygunluğunu mahalle bazında söyler — TÜFE ile bugüne endeksli.",
  "landing.why2Title": ".edu.tr ile güvende",
  "landing.why2Desc": "Sadece doğrulanmış üniversite öğrencileri. Sahte profil yok.",
  "landing.why3Title": "Bütçe haritası",
  "landing.why3Desc":
    "968 mahalle bütçene göre yeşil/sarı/kırmızı renklenir — hangi semtin bütçene uyduğunu tek bakışta gör.",
  "landing.footerListings": "İlanlar",

  // ---- keşfet (kaydırma) ----
  "swipe.emptyTitle": "Şimdilik bu kadar!",
  "swipe.emptyAll": "Mevcut tüm ilanlara karar verdin. Yeni ilan eklendiğinde burada görünecek.",
  "swipe.emptyFiltered": "Filtrelerine uyan ilan kalmadı. Filtreleri gevşetmeyi dene.",
  "swipe.clearFilters": "Filtreleri temizle",
  "swipe.matched": "Eşleştiniz! 🎉",
  "swipe.matchedDesc": "Eşleşmeni Beğeniler sayfasında görebilirsin.",
  "swipe.like": "BEĞENDİM ✓",
  "swipe.pass": "GEÇ ✗",
  "swipe.owner": "İlan Sahibi",

  // ---- adil fiyat ----
  "fair.fair": "Adil fiyat",
  "fair.above": "Piyasanın üstünde",
  "fair.below": "Piyasanın altında",
  "fair.title": "Adil Fiyat Analizi",
  "fair.body":
    "Bu oda için adil aralık {low} – {high} ₺ (orta {mid} ₺); istenen {asking} ₺, yani {sign}{dev}% farklı.",
  "fair.shared":
    "{bedrooms} yatak odası = {occupants} kişi; {areas} ortak kullanılıyor. Daire geneli {flatLow}–{flatHigh} ₺, kişi payı bu sayının {occupants}'e bölünmüşü.",
  "fair.footnote": "İlçe geneli tahmin · model medyan sapması %{err} · TÜFE ile güncellendi",

  // ---- ayarlar ----
  "settings.title": "Ayarlar",
  "settings.appearance": "Görünüm",
  "settings.language": "Dil",
  "settings.light": "Açık",
  "settings.dark": "Koyu",
  "settings.system": "Sistem",
  "settings.account": "Hesap Bilgileri",
  "settings.privacy": "Gizlilik ve Güvenlik",
  "settings.logout": "Çıkış Yap",
  "settings.loggedOut": "Çıkış yapıldı",

  // ---- giriş kapısı ----
  "gate.title": "Devam etmek için giriş yap",
  "gate.desc": "RoomMatch'te ev arkadaşı bulmak için ücretsiz hesap oluştur.",
  "gate.login": "Giriş Yap",
  "gate.signup": "Kayıt Ol",
  "gate.note": "Kayıt tamamen ücretsiz · .edu.tr gerekli",

  // ---- giriş ----
  "login.welcome": "Tekrar hoş geldin",
  "login.subPassword": "E-posta ve şifrenle giriş yap",
  "login.subOtp": "E-postana tek kullanımlık kod gönderelim",
  "login.tabPassword": "Şifre ile",
  "login.tabOtp": "Kodla gir",
  "login.emailPlaceholder": "öğrenci@üniversite.edu.tr",
  "login.passwordPlaceholder": "Şifren",
  "login.codePlaceholder": "6 haneli kod",
  "login.busy": "Bekleyin…",
  "login.submitLogin": "Giriş Yap",
  "login.submitVerify": "Kodu Doğrula",
  "login.submitSendCode": "Giriş Kodu Gönder",
  "login.resend": "Kodu tekrar gönder / e-postayı değiştir",
  "login.forgot": "Şifreni mi unuttun? Kodla gir →",
  "login.noAccount": "Hesabın yok mu?",
  "login.signupLink": "Kayıt ol →",
  "login.invalidEmail": "Geçerli bir e-posta adresi girin",
  "login.greet": "Hoş geldin{name}!",
  "login.devCode": "Giriş kodun: {code}",
  "login.codeSent": "Giriş kodu e-postana gönderildi!",
  "login.codeSentDesc": "Gelmesi birkaç saniye sürebilir; spam klasörünü de kontrol et.",
} as const;

export type TranslationKey = keyof typeof tr;

const en: Record<TranslationKey, string> = {
  // ---- common ----
  "common.save": "Save",
  "common.cancel": "Cancel",
  "common.back": "Back",
  "common.close": "Close",
  "common.delete": "Delete",
  "common.edit": "Edit",
  "common.loading": "Loading…",
  "common.retry": "Try again",
  "common.continue": "Continue",
  "common.perMonth": "/mo",
  "common.roomShare": "/mo per room",
  "common.currency": "₺",
  "common.houseListing": "Room offered",
  "common.personalListing": "Looking for a room",
  "common.error": "Something went wrong.",

  // ---- nav ----
  "nav.discover": "Discover",
  "nav.likes": "Likes",
  "nav.houses": "Listings",
  "nav.map": "Map",
  "nav.messages": "Messages",
  "nav.profile": "Profile",
  "nav.theme": "Theme",
  "nav.language": "Language",
  "nav.themeLight": "Light theme",
  "nav.themeDark": "Dark theme",

  // ---- landing ----
  "landing.findHouse": "Find a room",
  "landing.findRoommate": "Find a roommate",
  "landing.budgetMap": "Budget map",
  "landing.safety": "Safety",
  "landing.howItWorks": "How it works",
  "landing.logout": "Log out",
  "landing.login": "Log in",
  "landing.getStarted": "Get started",
  "landing.heroLine1": "The right roommate,",
  "landing.heroFair": "fair",
  "landing.heroLine2": "rent included.",
  "landing.heroSub":
    "A matching platform for university students in Istanbul. Machine-learning rent advisor, a neighborhood budget map, and a verified student community.",
  "landing.ctaContinue": "Keep exploring",
  "landing.ctaFree": "Start free",
  "landing.ctaBrowse": "Browse listings",
  "landing.statListings": "active listings",
  "landing.statNeighborhoods": "neighborhoods mapped",
  "landing.statError": "median model error",
  "landing.statErrorValue": "15.1%",
  "landing.eduBadge": "Sign-up only with a .edu.tr university email",
  "landing.featuredTitle": "Featured homes",
  "landing.featuredSub": "With per-room prices",
  "landing.stepsEyebrow": "Find a roommate in 3 steps",
  "landing.stepsTitle": "It's that simple.",
  "landing.step1Title": "Create your profile",
  "landing.step1Desc":
    "Sign up with your university email. Set your budget, lifestyle and preferred districts.",
  "landing.step2Title": "Discover and swipe",
  "landing.step2Desc":
    "Browse real listings and swipe right on the ones you like. The fair-price advisor tells you whether the rent matches the market.",
  "landing.step3Title": "Match and meet",
  "landing.step3Desc":
    "A mutual like creates a match. Talk safely through in-app messaging.",
  "landing.signupFree": "Sign up free",
  "landing.signupNote": "No credit card · Completely free · .edu.tr required",
  "landing.districtsTitle": "Search across Istanbul",
  "landing.districtsSub": "Districts with the most listings and their median room shares",
  "landing.districtCount": "{count} listings",
  "landing.districtMedian": "~{price} ₺/mo per room",
  "landing.why1Title": "Fair-price advisor",
  "landing.why1Desc":
    "A LightGBM model tells you whether the asking rent fits the market for that neighborhood — indexed to today with CPI.",
  "landing.why2Title": "Safe with .edu.tr",
  "landing.why2Desc": "Verified university students only. No fake profiles.",
  "landing.why3Title": "Budget map",
  "landing.why3Desc":
    "968 neighborhoods colored green/yellow/red against your budget — see at a glance which ones you can afford.",
  "landing.footerListings": "Listings",

  // ---- discover (swipe) ----
  "swipe.emptyTitle": "That's everything for now!",
  "swipe.emptyAll": "You've reviewed every available listing. New ones will show up here.",
  "swipe.emptyFiltered": "No listings match your filters. Try loosening them.",
  "swipe.clearFilters": "Clear filters",
  "swipe.matched": "It's a match! 🎉",
  "swipe.matchedDesc": "You can find it on the Likes page.",
  "swipe.like": "LIKED ✓",
  "swipe.pass": "PASS ✗",
  "swipe.owner": "Listing owner",

  // ---- fair price ----
  "fair.fair": "Fair price",
  "fair.above": "Above market",
  "fair.below": "Below market",
  "fair.title": "Fair-price analysis",
  "fair.body":
    "The fair range for this room is {low} – {high} ₺ (mid {mid} ₺); the asking price is {asking} ₺, i.e. {sign}{dev}% off.",
  "fair.shared":
    "{bedrooms} bedrooms = {occupants} people; {areas} are shared. The whole flat runs {flatLow}–{flatHigh} ₺, and each share is that divided by {occupants}.",
  "fair.footnote": "District-level estimate · model median error {err}% · CPI-indexed",

  // ---- settings ----
  "settings.title": "Settings",
  "settings.appearance": "Appearance",
  "settings.language": "Language",
  "settings.light": "Light",
  "settings.dark": "Dark",
  "settings.system": "System",
  "settings.account": "Account details",
  "settings.privacy": "Privacy and safety",
  "settings.logout": "Log out",
  "settings.loggedOut": "Logged out",

  // ---- auth gate ----
  "gate.title": "Log in to continue",
  "gate.desc": "Create a free account to find a roommate on RoomMatch.",
  "gate.login": "Log in",
  "gate.signup": "Sign up",
  "gate.note": "Signing up is free · .edu.tr required",

  // ---- login ----
  "login.welcome": "Welcome back",
  "login.subPassword": "Log in with your email and password",
  "login.subOtp": "We'll send a one-time code to your email",
  "login.tabPassword": "With password",
  "login.tabOtp": "With a code",
  "login.emailPlaceholder": "student@university.edu.tr",
  "login.passwordPlaceholder": "Your password",
  "login.codePlaceholder": "6-digit code",
  "login.busy": "Please wait…",
  "login.submitLogin": "Log in",
  "login.submitVerify": "Verify code",
  "login.submitSendCode": "Send login code",
  "login.resend": "Resend the code / change email",
  "login.forgot": "Forgot your password? Use a code →",
  "login.noAccount": "Don't have an account?",
  "login.signupLink": "Sign up →",
  "login.invalidEmail": "Enter a valid email address",
  "login.greet": "Welcome{name}!",
  "login.devCode": "Your login code: {code}",
  "login.codeSent": "Login code sent to your email!",
  "login.codeSentDesc": "It may take a few seconds; check your spam folder too.",
};

export const translations = { tr, en } as const;
