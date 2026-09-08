# 🏗️ Qurilish Materiallari Korxonasi — v3.0 (Bot + Python API + Node.js Web)

Qurilish materiallari **ishlab chiqarish + ulgurji savdo + ombor** uchun yagona tizim.

| Qatlam | Texnologiya | Port |
| :--- | :--- | :--- |
| 🤖 **Telegram Bot** | Python **aiogram v3.22** | — (polling) |
| 🔌 **REST API (Backend)** | Python **FastAPI** + SQLAlchemy | `8000` |
| 🌐 **Web Frontend** | **Node.js** (zero-dependency server) | `3000` |
| 💾 **Database** | SQLite (default) / PostgreSQL (sozlansa) | — |

```
Node.js (web/public)  ──proxy /api──▶  Python FastAPI (:8000)  ──▶  SQLite/PostgreSQL
        │                                    ▲
        └──────────────  Telegram Bot (aiogram v3) ────────────┘
```

---

## 🚀 Ishga tushirish

### 1) Backend + Bot (Python)

```bash
pip install -r requirements.txt
cp .env.example .env          # BOT_TOKEN, ADMIN_IDS ni kiriting

# REST API (Node.js frontend buni chaqiradi)
python -m uvicorn dashboard.app:app --port 8000

# Telegram bot (ayni database bilan ishlaydi)
python main.py
```

### 2) Web Frontend (Node.js — qo'shimcha kutubxona kerak emas!)

```bash
cd web
PORT=3000 PY_API_URL=http://127.0.0.1:8000 node server.js
# yoki: npm start
```

Keyin brauzerda: **http://localhost:3000**

> Node serveri `web/public` dan statik fayllarni xizmat qiladi va `/api/*`
> so'rovlarini Python backend'iga proxylaydi — `npm install` shart emas.

### 🔐 Web Dashboard — kirish (auth)

v3 dan boshlab **barcha `/api/*` so'rovlari himoyalangan** — xodimlar
(bot'dagi xodimlar) telefon raqami va parol bilan kiradi:

```bash
# 1) Xodimga parol o'rnatish (direktor/CLI orqali):
python -m dashboard.auth set-password --phone +998901234567 --password parol1234

# yoki birinchi ishga tushirishda .env'ga qo'ying (adminlarga avtomatik):
# WEB_ADMIN_PASSWORD=parol1234
```

- Login: `POST /api/login {phone, password}` → `{token, refresh_token, user}`
  (access + refresh token, `expires_in` bilan)
- Access token `Authorization: Bearer <token>` sarlavhasi bilan yuboriladi
  (Node proxy avtomatik uzatadi, token brauzerda `localStorage`da saqlanadi)
- **Refresh token**: `POST /api/refresh {refresh_token}` — muddati o'tgan access
  tokenni yangilaydi. Har refresh'da refresh token **aylantiriladi** (rotatsiya) va
  sessiya muddati **sliding** uzayadi (`REFRESH_TOKEN_TTL_DAYS`, default 30 kun).
  Node UI access muddati tugasa avtomatik refresh qilib so'rovni takrorlaydi.
- **Logout**: `POST /api/logout` (access header yoki `{refresh_token}` bilan) —
  sessiya server tomonda **revoke** qilinadi; eski access ham refresh ham ishlamaydi.
  Sessiyalar `web_sessions` jadvalida (refresh token sha256 xeshi bilan) saqlanadi.
- **Parolni unutdingizmi (self-service)**: login ekranida «Parolni unutdingizmi?» →
  so'rov beriladi → admin «🔐 Rollar» sahifasida so'rovni tasdiqlaydi va bir martalik
  kodni xodimga yetkazadi (kod `RESET_CODE_TTL_HOURS` soat amal qiladi, default 2 soat;
  ochiq saqlanmaydi — sha256 xeshi) → xodim kod + yangi parolni kiritadi. Parol
o'rnatilgach barcha web sessiyalari avtomatik revoke qilinadi. Kod bir martalik.
- Har bir endpoint rol matritsasi bo'yicha tekshiriladi: `direktor`, `sotuvchi`,
  `kassir`, `omborchi`, `haydovchi`, `buxgalter`, `ishchi` (config.py `ROLES`)
- Web UI rolga qarab menyu bo'limlarini ko'rsatadi/berkitadi; `see_cost=false`
  bo'lgan rollar uchun tannarx/narx maydonlari **server tomonda** kesiladi
  (CostVisibilityMiddleware)
- Parollar PBKDF2 bilan xeshlanadi, access token HMAC-SHA256 bilan imzolanadi,
  refresh token sha256 xeshlangan holda DB'da saqlanadi (qo'shimcha kutubxona
  shart emas). Maxfiy kalit: `API_SECRET_KEY` env yoki avtomatik yaratilgan
  `.web_secret` fayli

Qo'shimcha buyruqlar:
```bash
python -m dashboard.auth list-users        # xodimlar va parol holati
```

---

## 💳 Onlayn to'lovlar (Click / Payme)

Mijoz qarzini (nasiya) **Click** yoki **Payme** ilovasida to'lashi mumkin:

1. **`.env` ga kalitlarni kiriting:** `CLICK_MERCHANT_ID`, `CLICK_SERVICE_ID`,
   `CLICK_SECRET_KEY` (Click kabineti) va `PAYME_MERCHANT_ID`, `PAYME_KEY`
   (Payme Business kabineti). Ixtiyoriy: `PAYMENT_RETURN_URL`.
2. **Webhook manzillarini to'lov tizimiga berasiz:**
   - Click kabinetiga: `https://<domen>/api/payments/click`
   - Payme kabinetiga: `https://<domen>/api/payments/payme`
3. **Schyot-faktura yaratish** (kassir/direktor, CRM yoki Finance bo'limida):
   ```bash
   curl -X POST http://localhost:8000/api/payments/invoice \
     -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
     -d '{"gateway": "click", "amount": 150000, "customer_id": 5}'
   ```
   Javobda `links.click` / `links.payme` — mijozga yuboradigan to'lov havolasi.
4. Mijoz to'lagach, webhook to'lovni avtomatik tasdiqlaydi:
   - Click: `prepare` → `complete` (MD5 imzo tekshiriladi)
   - Payme: `CheckPerformTransaction` → `CreateTransaction` → `PerformTransaction`
   - To'lov `Payment` sifatida qayd etiladi va mijoz qarzi FIFO bo'yicha yopiladi.

> ⚠️ Click SHOP API ulangan bo'lishi kerak (kabinetda «Secret key» o'rnatilgan).
> Webhook'lar ochiq (`/api/payments/*`) — ular tashqi imzo/parol bilan himoyalangan, Bearer token shart emas.

---

## 🆕 v3.0 da qo'shilgan modullar (TZ asosida)

| Modul | Bot | API | Node UI | Tavsif |
| :--- | :-: | :-: | :-: | :--- |
| 👥 **CRM / Mijozlar** | ✅ | ✅ | ✅ | Mijoz kartasi, nasiya limiti, qarz FIFO to'lovi, sodiqlik ballari |
| 💰 **Sotuv (nasiya)** | ✅ | — | ✅ | Kredit limit tekshiruvi, oldindan to'lov, **aralash to'lov** (naqd+karta+nasiya bir chekda), chegirma (rol limiti) |
| 🚚 **Yetkazib beruvchilar** | ✅ | ✅ | ✅ | Ta'minot, sifat nazorati bilan qabul akti, kamomad qarzi, reyting |
| 📦 **Qabul aktlari** | ✅ | ✅ | ✅ | QA aktlari, tarozidagi farq → schyot-faktura |
| 🔒 **Rezervatsiya** | ✅ | ✅ | ✅ | Mahsulotni 2–24 soatga bloklash, muddat tugasa avto-yechish |
| 🔄 **Ko'chirish** | ✅ | ✅ | ✅ | Omborlararo (xomashyo/tayyor/brak) ko'chirish akti |
| 📋 **Inventarizatsiya** | ✅ | — | ✅ | Tizim ↔ haqiqiy solishtirish, yetishmovchilik dalolatnomasi |
| 💱 **Konvertatsiya** | ✅ | ✅ | — | 1 pallet = 40 qop = 2000 kg kabi o'lchov konvertatsiyasi |
| 📊 **Moliya (P&L)** | ✅ | ✅ | ✅ | Foyda/zarar, QQS 12%, aylanma soliq 4%, debitorlik qarzi, qaytarishlar |
| ↩️ **Qaytarish akti** | ✅ | ✅ | — | Mijoz tovarni qaytarsa: pul/karta, almashtirish (narx farqi), bonus ball; 7 kun qoidasi; brak ombori; P&L tuzatishi |
| 🚚 **Yetkazib berish (GPS)** | ✅ | ✅ | — | Sotuvga haydovchi tayinlash, marshrut, Telegram orqali jonli GPS kuzatuv (nuqtalar tarixi), yetkazib berilganini belgilash |
| 🏭 **Ishlab chiqarish** | ✅ | — | ✅ | Buyurtma, BOM/retsept bo'yicha xom ashyo hisobi, xarajat/foyda, statistik |
| 🔬 **Sifat nazorati (QC)** | ✅ | ✅ | — | Tayyor mahsulot chiqishida tekshiruv akti (SQC-…): ✅ qabul / ⚠️ qisman (rad miqdori) / ❌ rad; faqat qabul qilingani omborga kiradi, brak alohida qayd etiladi; bitta buyurtma uchun bir marta |
| 💳 **Qarz SMS eslatmalari** | ✅ (avto) | — | — | Muddati o'tgan nasiya qarzi uchun 3/7/14/30-kunlik bir martalik SMS (fon vazifasi, `DEBT_REMINDER_DAYS` sozlanadi) |
| 🕰️ **Sekin sotiladigan zaxira** | ✅ (avto) | — | — | `SLOW_STOCK_DAYS` (30) kundan beri harakatlanmagan mahsulot/xom ashyo ombor qoldig'i bilan ogohlantiriladi; tovar harakatga qaytsa qayta hisobga olinadi (fon vazifasi) |
| 💾 **Avtomatik backup** | ✅ | ✅ | ✅ | Har kuni `BACKUP_TIME` (02:00) da SQLite online-backup orqali konsistent nusxa (`backups/backup_*.db`), `BACKUP_KEEP_DAYS` (30) dan eskilari o'chadi; `BACKUP_NOTIFY` bo'lsa adminlarga xabar + audit log |
| ♻️ **Backupdan tiklash** | ✅ | ✅ | ✅ | Backup faylni tanlab databaseni qaytarish: avval joriy holatning xavfsizlik nusxasi olinadi, so'ng atomik almashtirish (os.replace) + integrity tekshiruvi; `backup_*.db` fayllargina tiklanadi |
| ☁️ **Backup → bulut/kanal** | ✅ (avto) | — | — | Har bir backup fayl `BACKUP_UPLOAD` da ko'rsatilgan manzillarga avtomatik yuklanadi: `telegram` (kanal, 50 MB gacha), `s3` (AWS S3/MinIO/Wasabi/Spaces — SigV4, boto3 shart emas) yoki `telegram,s3` (ikkalasi). Uzoq nusxalar `BACKUP_REMOTE_KEEP_DAYS` (standart 30) dan oshsa avtomatik o'chiriladi (S3: LIST+DELETE, Telegram: `delete_message`) |
| 🔐 **Backup shifrlash** | ✅ (avto) | — | — | `BACKUP_ENCRYPTION_PASSWORD` qo'yilsa serverdan chiqadigan nusxa PBKDF2-200k+AES bilan shifrlanadi va `.enc` sifatida yuklanadi (lokal nusxa ochiq qoladi); ochish: `decrypt_backup_file()` |
| 📋 **Backup tarixi (UI)** | ✅ | ✅ | ✅ | Botda «💾 Backup va tiklash» (olish/tarix/tiklash), web dashboardsa «💾 Backup» sahifasi: fayl nomi, hajmi (MB/B), yaratilgan sana, rejali backup sozlamalari |
| 🛒 **Ommaviy web-do'kon** | — | ✅ (public) | ✅ | Catalog + savat + checkout (`/shop.html`): naqd, Click/Payme yoki **aralash (Click/Payme + Naqd)** — naqd qismi yetkazishda, qolgani onlayn; to'lov tasdiqlangach buyurtma aralash Payment'lar bilan Sale'ga aylanadi |
| 💵 **Smena (kassa)** | ✅ | ✅ | — | Smena boshlash (boshlang'ich naqd), naqd kirim/chiqim guruhlari, kutilgan naqd, yopishda haqiqiy sanalgan bilan farq (kamomad/ortiqcha) |
| 🏅 **Mijoz triaji (Oltin/Kumush/Bronza)** | ✅ | ✅ | ✅ | Mijozlar xarid summasiga qarab avtomatik toifalanadi (TZ: "Kim ko'p va tez to'laydi — Oltin mijoz"); qarz >50% yoki muddati o'tgan qarz bo'lsa daraja pasayadi; bot kartasi, web jadval va `/api/customers/segmentation` |
| 💡 **O'xshash mahsulot taklifi** | ✅ | ✅ | — | Sotuvda mahsulot tanlanganda bir xil kategoriyadagi o'xshash mahsulotlar taklif qilinadi (TZ: "Bu g'ishtga mos sement va armatura" — o'rtacha chek oshadi); `GET /api/products/{id}/related` |
| 🚨 **Katta chegirma ogohlantirishi** | ✅ | — | — | Sotuvchi rol limitidan ortiq chegirma berishga urinsa sotuv bloklanadi, direktor(lar)ga Telegram ogohlantirishi + audit log yoziladi (TZ: "ikki bosqichli tasdiq") |
| 📊 **Direktor kunlik digesti** | ✅ (avto) | — | — | Har kuni ertalab yuboriladigan hisobot boyitildi: sotuvlar, eng ko'p sotilgan mahsulot, nasiya qarzlari, kechiktirilganlar, past zaxira, bugun tugashi kerak buyurtmalar |

> 🔀 **Aralash to'lov:** «🛒 Yangi sotuv» da «🔀 Aralash to'lov» tanlanadi → chegirma →
> naqd qismi → karta qismi → qolgan qism usuli (nasiya/Payme/Click/o'tkazma, nasiya
> uchun kredit limit tekshiriladi). Har bir usul alohida `Payment` qatori bo'ladi
> (`Sale.payment_method = "mixed"`), sodiqlik ballari faqat to'langan qismga beriladi,
> kassir smenasida faqat naqd qismi hisoblanadi.
>
> 💾 **Backup/restore:** botda `👑 Admin paneli → 💾 Backup va tiklash`, web'da
> `💾 Backup` sahifasi (faqat direktor). Tiklashdan oldin joriy holatning
> avtomatik xavfsizlik nusxasi olinadi (`backups/backup_*.db`), keyin fayl atomik
> almashtiriladi — tizim to'xtatilmaydi, yangi ulanishlar tiklangan faylni o'qiydi.
> `.env` misol (ikkalasi ham birga ishlaydi):
> ```ini
> BACKUP_UPLOAD=telegram,s3
> BACKUP_TELEGRAM_CHANNEL_ID=-1001234567890        # bot admin bo'lgan kanal
> BACKUP_S3_ENDPOINT=https://s3.amazonaws.com       # yoki MinIO: http://localhost:9000
> BACKUP_S3_BUCKET=my-company-backups
> BACKUP_S3_ACCESS_KEY=...
> BACKUP_S3_SECRET_KEY=...
> BACKUP_ENCRYPTION_PASSWORD=...                    # qo'yilsa — chiqish shifrlanadi
> BACKUP_REMOTE_KEEP_DAYS=30                        # uzoq joyda necha kun saqlanadi (0=o'chirilgan)
> ```
> S3'ga `backups/YYYY/MM/fayl.db` (yoki `.db.enc`) sifatida SigV4 imzolangan PUT
> orqali yuklanadi — boto3 kerak emas, har qanday S3-mos xizmat ishlaydi.
> **Uzoq joyda saqlash muddati:** har bir backup ishga tushganda eski uzoq nusxalar
> ham tozalanadi (`prune_remote_backups`). S3 da bucket ListObjectsV2 bilan
> ro'yxatlanib eski `backup_*.db[.enc]` ob'ektlar DELETE qilinadi (funksiyadan
> oldin yuklanganlar ham); Telegram da Bot API kanal tarixini ro'yxatlay
> olmagani uchun yuborilgan xabarlarning `message_id` si `telegram_backup_messages`
> jadvalida saqlanadi va eskilari `delete_message` orqali o'chiriladi (faqat shu
> funksiyadan keyin yuborilganlar — oldingi xabarlar kanalda qoladi).
> Shifrlangan nusxani ochish:
> `python -c "from utils.backup import decrypt_backup_file; print(decrypt_backup_file('backup_....db.enc'))"`
| 🔐 **Rollar matritsasi** | ✅ | ✅ | ✅ | Direktor/Sotuvchi/Kassir/Omborchi/Haydovchi/Buxgalter/Ishchi |
| 🏷️ **Narxlar** | — | — | ✅ | Ulgurji/chakana narx maydonlari |

### Rol matritsasi (qisqacha)

| Rol | Ko'ra oladi | O'zgartira oladi |
| :--- | :--- | :--- |
| 👑 Direktor | hammasi | hammasi (tannarx + 100% chegirma) |
| 🛒 Sotuvchi | sotuv, CRM, ombor, rezerv | sotuv, CRM, rezerv (5% gacha chegirma, tannarxni ko'rmaydi) |
| 💵 Kassir | sotuv | to'lov, smena |
| 📦 Omborchi | ombor, ta'minot, ko'chirish | kirim/chiqim, qabul akti (narxni ko'rmaydi) |
| 🚚 Haydovchi | ombor, ko'chirish, **yetkazib berish** | **yetkazib berish** (GPS kuzatuv, yakunlash) |
| 🧮 Buxgalter | moliya, hisobot, CRM | moliya |
| 🔧 Ishchi | ishlab chiqarish, ombor | — |

Rollarni botda: `👑 Admin paneli → 🔐 Rollar boshqaruvi` yoki `/rollar`.

---

## 🆕 v4.1 — Operatsion modullar (yoqilg'i, avans, yig'ish, xavfsizlik, reyting)

TZ bo'limlari A/D/4/F va "Xodim ish vaqti" asosida qo'shilgan modullar endi
**bot + API + Web dashboard** uch qatlamda ham ishlaydi:

| Modul | Bot | API | Web UI | Tavsif |
| :--- | :-: | :-: | :-: | :--- |
| ⛽ **Yoqilg'i nazorati** | ✅ | ✅ | ✅ | Haydovchi quyishni qayd etadi (litr, narx, spidometr); tizim L/100km hisoblab, me'yordan oshsa direktor ogohlantiriladi (`FUEL_NORM_LITERS_PER_100KM`) |
| 🧾 **Avans hisoboti** | ✅ | ✅ | ✅ | Xodim yo'l haqi/ovqat/benzin xarajatini qayd etadi, direktor/buxgalter tasdiqlaydi; tasdiqlanganlar moliyaviy hisobotga qo'shiladi |
| 📦 **Yig'ish varaqasi** | ✅ | ✅ | ✅ | Sotuv/shop buyurtmasi bo'yicha omborchi uchun ro'yxat (sektor bilan), yuklovchi/omborchi "tayyor" deb belgilaydi |
| 🚨 **Shubhali harakat detektori** | ✅ | ✅ | ✅ | Tungi sotuv, katta chegirma, qaytarish ko'payishi va boshqa anomaliyalar avtomatik qayd etiladi, direktor hal qiladi |
| 🏆 **Sotuvchilar reytingi** | ✅ | ✅ | ✅ | Har bir sotuvchining 30 kunlik savdosi, chek soni va o'rtacha cheki |
| 🕰️ **Xodim ish vaqti** | ✅ | — | — | Kirish/chiqish vaqtini qayd etish, ishlagan va qo'shimcha soatlarni hisoblash (`handlers/employees.py`) |

Web dashboard sahifalari: `⛽ Yoqilg'i nazorati`, `🧾 Avans hisobotlari`,
`📦 Yig'ish varaqalari`, `🚨 Xavfsizlik`, `🏆 Sotuvchilar reytingi` —
API endpointlari (`/api/fuel/*`, `/api/expenses/*`, `/api/picking/*`,
`/api/security/*`, `/api/sellers/ratings`) bilan bog'langan.

---

## 🆕 v4.2 — 2FA: Google Authenticator (TZ: "Direktor va kassir uchun")

Paroldan tashqari **6 xonali bir martalik kod** bilan ikki bosqichli kirish:

| Qatlam | Holat | Izoh |
| :--- | :-: | :--- |
| Bot `/2fa` | ✅ | Yoqish: QR rasm + kalit, kod bilan tasdiqlash; o'chirish: joriy kod |
| Bot `/login` | ✅ | 2FA yoqilgan xodim paroldan keyin kod kiritadi |
| Web `/login` (HTML) | ✅ | Parol -> `otp_token` (5 daqiqa) -> kod |
| API `/api/login` | ✅ | Kodsiz so'rov 428, noto'g'ri kod 401, to'g'ri kod 200 |
| API `/api/auth/2fa/*` | ✅ | `setup` (secret+QR), `enable` (kod), `disable` (kod) |
| Web UI (Xavfsizlik sahifasi) | ✅ | Holat + yoqish/o'chirish oynalari (QR ko'rsatiladi) |
| `/api/me` | ✅ | `two_fa_enabled` maydoni |

Texnik jihatlar:
- TOTP **RFC 6238** — `utils/totp.py` (standart kutubxona; QR uchun `qrcode`,
  u allaqachon requirements.txt da bor).
- Secret `Employee.otp_secret` (base32) + `otp_enabled` ustunlarida; eski DB
  `upgrade_schema()` orqali avtomatik yangilanadi (ma'lumot o'chirilmaydi).
- Kod server tomonda tekshiriladi; 2FA o'chirilganda xavfsizlik uchun barcha
  web/bot sessiyalari bekor qilinadi.

---

## 🆕 v5 — To'liq REST API + narx tarixi + yangi Web sahifalar (TZ 2-bo'lim)

- **REST API v5** (`dashboard/api_v5.py`): spec'dagi API ro'yxati bo'yicha 70+ endpoint —
  Users CRUD, Products (search/import/narx→tarix), Categories CRUD, Orders (sotuv yaratish),
  Payments, Inventory (adjust/history), Reports (kunlik/haftalik/oylik/yillik/eksport),
  Suppliers, Production, Warehouses CRUD, Auth aliaslar (`/api/auth/*`).
- **Narx tarixi**: `product_price_history` jadvali — har narx o'zgarishi saqlanadi;
  API `GET /api/products/{id}/price-history`, bot `💱 Narx tarixi`.
- **Web UI 6 ta yangi sahifa** (`web/public/app_v5.js`): 💰 Sotuv (POS), 🏭 Ishlab chiqarish,
  🚚 Yetkazib berish (imzo + GPS), ↩️ Qaytarish, 💵 Smena (kassa), 🛒 Do'kon buyurtmalari.
- **PWA** (`manifest.json` + `sw.js`): mobil telefonda ilova kabi ishlaydi, offline rejim.

## 🆕 v5.1 — Tranzaksiya kodi, avans fotosi, mijoz ma'lumotlari shifrlash

Qayta to'liq audit (`construction_factory_bot.md` A–H "20+ nozik holat" bo'limlari)da
topilgan qolgan bo'shliqlar yopildi:

- **🔖 Tranzaksiya kodi** (TZ A-bo'lim): har bir sotuv, qaytarish akti va ombor
  kirim/chiqimiga unikal **16 xonali kod** (`YYMMDD`+10 raqam) — `sales`,
  `return_acts`, `warehouse_transactions` jadvallarida. Yangi qatorlarda avtomatik,
  eski DB'ga `upgrade_schema` backfill qiladi. Bot chekida `🔖 Tranzaksiya:` qatori.
- **🔎 Hujjat izlash**: `GET /api/documents/lookup?code=<16 raqam>` — soliq
  tekshiruvida hujjatni 1 daqiqada topish; web POS'da "🔍 Hujjat izlash" kartasi.
- **📎 Avans hisoboti fotosurati** (TZ A-bo'lim): `ExpenseReport.photo_path`;
  bot'da ixtiyoriy rasm qadami, direktor "🖼 rasmi" tugmasi bilan chekni ko'radi.
- **🔒 Mijozlar ma'lumotlari shifrlash** (TZ F-bo'lim): server tomonda
  `mask_customer_dict` — direktor/haydovchi to'liq telefon/manzilni ko'radi,
  sotuvchi va boshqa rollarga telefon maskalanadi (`+998 ** *** ** 45`),
  manzil/izoh yashiriladi.

## 🐳 Docker va CI/CD (TZ: Deploy bo'limi)

```bash
cd construction_factory_bot
cp .env.example .env          # BOT_TOKEN, ADMIN_IDS kiriting

docker-compose up -d --build
#   api  -> http://localhost:8000   (FastAPI)
#   web  -> http://localhost:3000   (Node.js frontend, /api -> api:8000)
#   bot  -> Telegram bot (polling)
```

- `Dockerfile` — Python 3.11 + Node.js 20 (yagona image).
- `docker-compose.yml` — 3 xizmat: api / web / bot; SQLite `database/`,
  backups, logs, reports papkalari bind-mount bilan saqlanadi.
- `.github/workflows/ci.yml` — har push/PR da: pytest (568+ test),
  Node.js sintaksis tekshiruvi va Docker build.

---

## 🆕 v4.0 — Xavfsizlik: LOGIN/PAROL + SESSIYA (bot va web)

TZ talabiga ko'ra har bir xodim tizimga **parol bilan kiradi** va qisqa muddatli
sessiya oladi. Sessiya tugaganda (muddat yoki harakatsizlik) yoki logout
gilganda xodimga berilgan **barcha darajalar (rol ruxsatlari) avtomatik bekor**
bo'ladi — keyingi amal uchun qayta `/login` kerak.

### Telegram bot

| Buyruq | Vazifasi |
| :--- | :--- |
| `/login` | Telefon raqam + parol bilan sessiya ochish (birinchi kirishda telegram ID avtomatik bog'lanadi) |
| `/sessiya` | Joriy sessiya holati: qolgan vaqt, harakatsizlik taymeri |
| `/logout` | Sessiyani bekor qilish — darajalar darhol o'chadi |
| `/parol` | Parolni o'rnatish/o'zgartirish (joriy parol bilan tasdiqlanadi) |

- Parollar **PBKDF2-HMAC-SHA256** bilan xeshlanadi (web dashboard bilan **bir xil
  format** — bir parol ham web, ham bot uchun ishlaydi).
- Parol xato kiritilsa `BOT_LOGIN_MAX_ATTEMPTS` (3) marta — hisob
  `BOT_LOGIN_LOCKOUT_MINUTES` (10 daqiqa) ga bloklanadi (bruteforce himoyasi).
- Parol o'zgarsa xodimning **barcha faol sessiyalari** (bot + web) bekor qilinadi.
- Har bir xabar/callback global middleware orqali sessiya tekshiruvidan o'tadi
  (`main.py`) — sessiyasiz faqat `/start`, `/help`, `/cancel`, `/login`, `/logout`,
  `/sessiya`, `/parol` ishlaydi.

### Web dashboard

- Access token muddati: `SESSION_MINUTES` (5–30 daqiqa, standart 15).
- Harakatsizlik: `SESSION_IDLE_MINUTES` (25 daqiqa) dan oshsa sessiya
  `idle_timeout` bilan o'ladi — keyingi so'rov 401 qaytaradi.
- `POST /api/logout` sessiyani revoke qiladi: eski access ham refresh ham ishlamaydi.
- `GET /api/me` javobida `session` (qolgan vaqt, idle) va `session_policy` bor —
  UI avto-logout uchun ishlatiladi.

### Direktor nazorati (API)

```
GET  /api/bot-sessions            Xodimlar bot sessiyalari tarixi (kim qachon kirdi, qanday tugagan)
GET  /api/bot-sessions/policy     Sessiya siyosati (muddat, idle, blok qoidalari)
POST /api/bot-sessions/revoke     Xodimning faol bot sessiyalarini bekor qilish
                                  {"employee_id": 5} yoki {"telegram_id": 123}
```

### Sessiya sozlamalari (.env)

```ini
BOT_AUTH_ENABLED=true                 # false bo'lsa eski rejim (telegram_id bo'yicha)
BOT_SESSION_MINUTES=15                # bot sessiya muddati (5..30 daqiqa, TZ)
BOT_SESSION_IDLE_MINUTES=25           # harakatsizlik limiti
BOT_LOGIN_MAX_ATTEMPTS=3              # xato parol limiti
BOT_LOGIN_LOCKOUT_MINUTES=10          # blok muddati
BOT_MAX_SESSIONS_PER_EMPLOYEE=2       # bir xodimga bir vaqtda nechta sessiya
SESSION_MINUTES=15                    # web access token muddati (5..30 daqiqa, TZ)
SESSION_IDLE_MINUTES=25               # web harakatsizlik limiti
REFRESH_TOKEN_TTL_DAYS=30             # web refresh token (sliding)
```

> Eski tizimga ziyon yetkazmaslik uchun `BOT_AUTH_ENABLED=false` qilsangiz bot
> avvalgi holatda (telegram_id bo'yicha ruxsat) ishlaydi. Web dashboard sessiyasi
> esa har doim qisqa muddatli token + revoke bilan ishlaydi.

---

## 🔌 REST API (Python)

Barcha endpointlar `http://localhost:8000/api/...` (Node.js frontend orqali `http://localhost:3000/api/...`):

```
POST /api/login                 Login (telefon+parol) -> access + refresh token
POST /api/refresh               Yangi access token (refresh token bilan, sliding)
POST /api/logout                Sessiyani revoke qilish (logout)
GET  /api/me                    Joriy foydalanuvchi va ruxsatlari
POST /api/password-reset/request     Parol tiklash so'rovi (auth shart emas)
POST /api/password-reset/complete    Kod bilan yangi parol o'rnatish (auth shart emas)
GET  /api/password-reset/requests    Tiklash so'rovlari (faqat admin)
POST /api/password-reset/{id}/approve   So'rovni tasdiqlash -> bir martalik kod (admin)
POST /api/password-reset/{id}/reject    So'rovni rad etish (admin)
GET  /api/stats                 Umumiy statistika
GET  /api/warehouse             Ombor (xom ashyo)
GET  /api/products              Mahsulotlar
GET  /api/products/{id}/units   O'lchov birliklari
POST /api/products/{id}/units   Birlik qo'shish
GET  /api/convert               Konvertatsiya (?product_id&from_unit&to_unit&quantity)
GET  /api/customers             Mijozlar (CRM)
POST /api/customers             Yangi mijoz
GET  /api/customers/{id}        Mijoz kartasi + tarix
POST /api/customers/{id}/pay    Qarz to'lash
GET  /api/suppliers             Yetkazib beruvchilar
POST /api/suppliers             Yangi yetkazib beruvchi
GET  /api/suppliers/reorder-suggestions   Avtomatik buyurtma
GET  /api/receipts              Qabul aktlari
POST /api/receipts              Qabul akti yaratish
GET  /api/reservations          Rezervatsiyalar
POST /api/reservations          Rezervatsiya yaratish
POST /api/reservations/{id}/cancel|complete
GET  /api/transfers             Ko'chirishlar
POST /api/transfers             Ko'chirish yaratish
GET  /api/inventory-checks      Inventarizatsiya varaqalari
POST /api/inventory-checks      Tekshiruv kiritish
GET  /api/finance/pl            Foyda/Zarar (P&L)
GET  /api/finance/tax           Soliq kalkulyatori
GET  /api/finance/debts         Qarzlar hisoboti
GET  /api/roles                 Xodimlar rollari (faqat admin)
POST /api/roles/{id}/password   Xodim web-parolini o'rnatish (faqat admin)
POST /api/payments/invoice      Onlayn to'lov schyot-fakturasi yaratish (Click/Payme havolasi)
GET  /api/payments/invoices     To'lov schyot-fakturalari ro'yxati
POST /api/payments/click        Click SHOP API webhook (prepare/complete, imzosiz — Click imzo bilan tekshiradi)
POST /api/payments/payme        Payme Merchant API webhook (JSON-RPC, Basic auth)
GET  /api/returns               Qaytarish aktlari ro'yxati
GET  /api/returns/candidates    Qaytarishga yaroqli sotuvlar
GET  /api/returns/{id}          Qaytarish akti tafsilotlari
POST /api/returns               Qaytarish akti yaratish (pul/almashtirish/bonus)
GET  /api/deliveries            Yetkazishlar (status/haydovchi filter bilan)
GET  /api/deliveries/deliverable-sales   Yetkazish mumkin sotuvlar
GET  /api/deliveries/{id}       Yetkazish + GPS nuqtalari
POST /api/deliveries            Topshiriq yaratish (haydovchi tayinlash)
POST /api/deliveries/{id}/start     Yetkazishni boshlash
POST /api/deliveries/{id}/location  GPS nuqtasini qayd qilish
POST /api/deliveries/{id}/complete  Yetkazib berishni yakunlash
POST /api/deliveries/{id}/cancel    Yetkazishni bekor qilish

# Ommaviy web-do'kon (auth shart emas) — Node orqali /api/shop/*
GET  /api/shop/catalog            Katalog (faol mahsulotlar + zaxiradagi miqdor)
GET  /api/shop/categories         Kategoriyalar
POST /api/shop/orders             Checkout: naqd (darhol Sale) yoki Click/Payme (havola)
GET  /api/shop/orders/{number}    Buyurtma holati (?phone= tasdiqlash bilan)
POST /api/shop/orders/{number}/cancel   To'lanmagan buyurtmani bekor qilish

# Do'kon buyurtmalari boshqaruvi (rol talab qilinadi)
GET  /api/shop-orders             Buyurtmalar ro'yxati (buxgalter/direktor)
POST /api/shop-orders/{id}/cancel Buyurtmani bekor qilish (admin)

# Kassir smenasi
GET  /api/cash-shifts             Smenalar ro'yxati (?status= ochiq|yopilgan)
GET  /api/cash-shifts/current     Joriy ochiq smena + kutilgan naqd hisob
POST /api/cash-shifts/open        Smena boshlash (opening_balance)
POST /api/cash-shifts/{id}/close  Smena yopish (actual_cash -> farq hisoblanadi)

# Database backup / restore (faqat direktor)
GET  /api/backups                 Backup tarixi: fayl nomi, hajmi, sana, sozlamalar
POST /api/backups                 Qo'lda backup olish (konsistent nusxa + eskilarni tozalash)
POST /api/backups/restore         Tiklash: {"filename": "backup_...db"} (avval xavfsizlik nusxasi olinadi)

**Auth:** barcha endpointlar talab qiladi — `Authorization: Bearer <token>`
(`POST /api/login` orqali olinadi; `GET /api/me` joriy foydalanuvchi va ruxsatlarini qaytaradi).
Ruxsatsiz: `401`; roli mos kelmasa: `403` — javob shakli `{"error": "..."}`.
```

---

## 🧪 Testlar

```bash
pytest                # 568+ test (bot, DB, API auth, utils, shop, smena, sessiya)
```

Testlar `tests/test_api/conftest.py` da admin (direktor) override bilan ishlaydi;
haqiqiy auth oqimi `tests/test_api/test_auth.py` da in-memory DB'da tekshiriladi.

---

## 📁 Papka tuzilishi (v3 qo'shimchalari)

```
dashboard/api_v3.py        # REST API v3 endpointlari
handlers/customers.py      # CRM moduli
handlers/suppliers.py      # Yetkazib beruvchilar + qabul aktlari
handlers/stock_ops.py      # Rezervatsiya, ko'chirish, inventarizatsiya, konvertatsiya
handlers/finance.py        # Moliya (P&L, qarz, soliq)
handlers/roles.py          # Rollar boshqaruvi
handlers/returns.py        # Qaytarish akti (pul/almashtirish/bonus) — bot
handlers/delivery.py       # Yetkazib berish + GPS kuzatuv (haydovchi) — bot
dashboard/shop.py          # Ommaviy web-do'kon API (catalog/savat/checkout)
web/public/shop.html       # Do'kon sahifasi (mijozlar uchun) — /shop.html
handlers/cash_shift.py     # Smena yopish + naqd farq (kassir) — bot
utils/access.py            # Ruxsatlar (rol matritsasi) yordamchisi
dashboard/payments.py      # Click/Payme webhook'lari
web/server.js              # Node.js web server (proxy)
web/public/index.html      # Yangi dizayn (SPA)
handlers/operations.py     # Yoqilg'i, avans, yig'ish, xavfsizlik, reyting (bot)
handlers/bot_auth.py       # Bot login/parol + sessiya (v4)
handlers/employees.py      # Xodimlar + ish vaqti
utils/bot_auth.py          # Bot sessiya logikasi (PBKDF2, login/lockout)
utils/rate_limit.py        # API rate limiting
Dockerfile                 # Yagona konteyner (Python + Node)
docker-compose.yml         # api / web / bot xizmatlari
../.github/workflows/ci.yml# CI: pytest + Node tekshiruvi + Docker build
database/models.py         # + Customer, Payment, ReturnAct, Delivery, DeliveryLocation, Supplier, ProductUnit, Reservation, InventoryCheck, FuelLog, ExpenseReport, PickingList, SuspiciousActivity, WebSession, EmployeeAuthSession
```
