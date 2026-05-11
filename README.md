# Formo Renovation — Report Generator

Upload a CompanyCam PDF → get a branded Before & After report in seconds.

---

## Deploy to Render (free) — 5 steps

### 1. Put these files on GitHub

Go to github.com → New repository → name it `formo-report-generator`

Upload all these files:
```
app.py
Dockerfile
render.yaml
requirements.txt
templates/index.html
```

### 2. Create Render account

Go to render.com → Sign up free (use GitHub login)

### 3. Create new Web Service

- Click **New** → **Web Service**
- Connect your GitHub repo `formo-report-generator`
- Render auto-detects the Dockerfile
- Name: `formo-report`
- Instance type: **Free**
- Click **Deploy**

### 4. Add your Anthropic API key (for AI descriptions)

In Render dashboard → your service → **Environment**:
```
ANTHROPIC_API_KEY = sk-ant-your-key-here
```

*(Skip this if you only need the Client version without descriptions)*

### 5. Done

Your app is live at: `https://formo-report.onrender.com`

---

## How to use

1. Open the URL on iPad, iPhone, or any browser
2. Upload your CompanyCam Before & After PDF
3. Choose:
   - **Client Version** — photos + titles, clean for sending
   - **With Descriptions** — AI writes 2-line caption per photo (needs API key)
4. PDF downloads automatically

---

## Notes

- Free Render tier sleeps after 15 min of inactivity — first request after sleep takes ~30 seconds to wake up
- Upgrade to Render Starter ($7/mo) to keep it always-on
- Max upload: 100MB
- Processing time: ~30–60 seconds per report

---

## Update the branding

All brand colors are in `app.py` in the `build_html()` function CSS section.
Colors: `--g: #C9A96E` (gold), `--b: #191816` (dark background)
