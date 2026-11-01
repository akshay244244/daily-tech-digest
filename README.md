# Daily Tech Digest — Free edition

Tumhari personal daily tech news website. **Bilkul free**: GitHub Actions roz news laata hai, Gemini (free tier) usse curate karta hai, GitHub Pages pe site live hoti hai, aur Gmail se email aata hai.

- Roz **06:30 IST** naya digest + email (agar miss ho jaye to 09:00 IST pe catch-up)
- Har **Sunday 18:30 IST** weekly recap + email
- 5 sections, Today's top 5, 7-day section pages, story detail panel, search, saved, weekly recap, quiz
- 4 site styles (Classic + dark mode, Soft Glass, Vibrant Pop, Bold Brutalist)

---

## Setup (ek baar, ~20 minute)

### 1. GitHub pe repo banao
1. https://github.com pe account banao (agar nahi hai).
2. Upar right mein **+** → **New repository**.
3. Name: `daily-tech-digest` · **Public** chuno (free Pages ke liye public zaroori hai) → **Create repository**.

### 2. Files upload karo
1. Zip ko apne computer pe extract karo.
2. Repo page pe **uploading an existing file** link dabao.
3. Extracted folder ke **andar ki saari cheezein** (`digest`, `site`, `.github`, `requirements.txt`, `README.md`, `.gitignore`) drag karke daalo → **Commit changes**.
4. Check karo ki repo mein `.github/workflows/digest.yml` dikh raha hai.
   Agar `.github` folder upload nahi hua (kabhi kabhi hidden folder skip ho jaata hai):
   **Add file → Create new file** → naam mein likho `.github/workflows/digest.yml` → zip wali file ka content paste karo → Commit.

### 3. Gemini API key lo (free)
1. https://aistudio.google.com/apikey kholo, Google account se login karo.
2. **Create API key** → key copy kar lo.
   (Key na bhi daalo to site chalegi — bas AI ki jagah simple fallback use hoga.)

### 4. Gmail App Password banao (email ke liye)
1. Google account mein **2-Step Verification** on hona chahiye: https://myaccount.google.com/security
2. https://myaccount.google.com/apppasswords kholo → naam `Digest` → **Create**.
3. 16 letters ka password dikhega — copy kar lo. (Ye tumhara normal Gmail password nahi hai.)

### 5. Secrets daalo
Repo → **Settings → Secrets and variables → Actions → New repository secret**. Ye 3 (ya 4) banao:

| Name | Value |
|---|---|
| `GEMINI_API_KEY` | Step 3 wali key |
| `GMAIL_USER` | tumhari gmail id, e.g. `you@gmail.com` |
| `GMAIL_APP_PASSWORD` | Step 4 wala 16-letter password |
| `EMAIL_TO` | *(optional)* kis email pe bhejna hai. Khaali chhodo to `GMAIL_USER` pe jayega |

### 6. Permissions aur Pages on karo
1. **Settings → Actions → General** → neeche **Workflow permissions** → **Read and write permissions** → Save.
2. **Settings → Pages** → **Source: GitHub Actions**.

### 7. Pehla run (backfill — pichhle 7 din ka data)
1. Repo ka **Actions** tab kholo. Agar "enable workflows" ka button dikhe to dabao.
2. Left mein **Daily Tech Digest** → right mein **Run workflow** → task: **backfill** → **Run workflow**.
3. 10–20 minute lagenge. Green ✓ aane ke baad site live:
   **`https://<tumhara-github-username>.github.io/daily-tech-digest/`**
   (Exact link: Settings → Pages pe bhi dikhega.)

### 8. Email test karo
Actions → Daily Tech Digest → Run workflow → task: **daily** → Run. Kuch minute mein email aana chahiye (Spam folder bhi check karna; pehli baar "Not spam" mark kar dena).

Bas! Ab roz subah apne aap chalega.

---

## Kaise kaam karta hai
```
GitHub Actions (cron)  →  python -m digest.main daily
   fetch RSS + Google News → duplicates hatao → Gemini curation (ya fallback)
   → article se image + summary → site/data/*.json mein save → repo mein commit
   → GitHub Pages pe deploy → Gmail se email
Website (site/)  →  sirf JSON padhti hai, isliye turant load hoti hai
```

## Free version ki limits (jaan lo)
- **Refresh now** button GitHub ka workflow page kholta hai — wahan "Run workflow" dabana hota hai. Site 3–5 min mein khud update ho jaati hai.
- GitHub ka schedule kabhi kabhi **5–30 min late** chalta hai.
- **Saved** stories isi browser mein save hoti hain (phone aur laptop alag).
- **Search** aur **"Ask about this story"** keyword matching se chalte hain (browser se AI call karne ke liye key public karni padti, jo safe nahi).
- **Detailed summary** aur **quiz** Gemini se bante hain jab key ho; nahi to extractive summary aur headline quiz.
- Kuch sites (paywall, Reddit) article text ya image block kar sakti hain — tab gradient placeholder dikhega.

## Settings badalni ho to
- Sections, feeds, search queries, Adobe-competitor list: `digest/config.py`
- Time badalna: `.github/workflows/digest.yml` mein cron (UTC mein hota hai; IST = UTC + 5:30)
- Gemini model: Settings → Secrets and variables → Actions → **Variables** tab → `GEMINI_MODEL` (default `gemini-flash-latest`)
- Custom domain: variable `SITE_URL` set karo taaki email links sahi jaayein

## Agar kuch na chale
- Actions tab mein failed run kholo → red step pe click → error padho.
- `AI disabled ... HTTP 400/403` → Gemini key galat hai ya model naam badal gaya (`GEMINI_MODEL` variable set karo, e.g. AI Studio mein dikhne wala flash model).
- `Email failed: ... Username and Password not accepted` → App Password dobara banao, spaces ke saath ya bina dono chalega.
- Site 404 → Settings → Pages → Source "GitHub Actions" hai na? Aur ek run green hua hai na?
