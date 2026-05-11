import os, base64, subprocess, tempfile, re
from flask import Flask, request, jsonify, send_file, render_template
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB max

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ── Helpers ────────────────────────────────────────────────────────────────

def extract_images(pdf_path, out_dir):
    """Extract images from PDF using pdfimages."""
    prefix = os.path.join(out_dir, "img")
    subprocess.run(["pdfimages", "-j", pdf_path, prefix],
                   check=True, capture_output=True)
    imgs = sorted(
        [os.path.join(out_dir, f) for f in os.listdir(out_dir)
         if re.match(r"img-\d+\.jpe?g$", f, re.IGNORECASE)],
        key=lambda p: int(re.search(r"(\d+)", os.path.basename(p)).group(1))
    )
    return imgs

def extract_meta(pdf_path):
    """Pull project name, address, date from PDF text."""
    try:
        result = subprocess.run(["pdftotext", "-layout", pdf_path, "-"],
                                capture_output=True, text=True, check=True)
        text = result.stdout
    except Exception:
        return {"project": "Project", "address": "", "date": ""}
    meta = {"project": "", "address": "", "date": ""}
    m = re.search(r"Before\s*&\s*After\s+([^\n]{3,60})", text, re.IGNORECASE)
    if m: meta["address"] = m.group(1).strip()
    m = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}", text, re.IGNORECASE)
    if m: meta["date"] = m.group(0)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for i, line in enumerate(lines):
        if "formo" in line.lower() and i > 0:
            c = lines[i - 1]
            if len(c) < 50 and not re.search(r"\d{4}|before|after|renovation", c, re.I):
                meta["project"] = c; break
    return meta

def img_to_b64(path):
    with open(path, "rb") as f:
        return f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"

def font_to_b64(path):
    with open(path, "rb") as f:
        return f"data:font/truetype;base64,{base64.b64encode(f.read()).decode()}"

def ai_describe(img_path, num):
    """Call Claude to get 2-line English description."""
    if not ANTHROPIC_KEY:
        return {"section": "General", "title": f"Photo {num}",
                "description": "", "tags": []}
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-20250514", max_tokens=180,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                {"type": "text", "text": f"""Before/after renovation photo #{num}. BEFORE=left, AFTER=right.
Reply ONLY valid JSON:
{{"section":"<Exterior|Deck|Doors|Flooring|Bathrooms|Kitchen|Paint & Drywall|Windows & Lighting|Trim & Molding|Utilities|General>","title":"<4-6 word English title>","description":"<EXACTLY 2 short English sentences. First: problem before. Second: what was done. Max 18 words each.>","tags":["<tag1>","<tag2>"]}}"""}
            ]}]
        )
        text = msg.content[0].text.strip().replace("```json","").replace("```","").strip()
        import json; return json.loads(text)
    except Exception:
        return {"section": "General", "title": f"Photo {num}",
                "description": "Renovation work completed.", "tags": []}

def build_fonts_css():
    LIB = "/usr/share/fonts/truetype/liberation/"
    if not os.path.exists(LIB):
        return ""  # fallback to system fonts
    try:
        return f"""
@font-face{{font-family:'DS';font-weight:300;font-style:normal;src:url('{font_to_b64(LIB+"LiberationSerif-Regular.ttf")}') format('truetype');}}
@font-face{{font-family:'DS';font-weight:300;font-style:italic;src:url('{font_to_b64(LIB+"LiberationSerif-Italic.ttf")}') format('truetype');}}
@font-face{{font-family:'BS';font-weight:300;src:url('{font_to_b64(LIB+"LiberationSans-Regular.ttf")}') format('truetype');}}
@font-face{{font-family:'BS';font-weight:700;src:url('{font_to_b64(LIB+"LiberationSans-Bold.ttf")}') format('truetype');}}
"""
    except Exception:
        return ""

def build_html(meta, photos, include_descriptions):
    """Build the full branded HTML report."""
    project = meta.get("project", "Project")
    address = meta.get("address", "")
    date    = meta.get("date", "")

    ORDER = ["Exterior","Deck","Doors","Flooring","Bathrooms","Kitchen",
             "Paint & Drywall","Windows & Lighting","Trim & Molding","Utilities","General"]
    grouped = {}
    for p in photos:
        grouped.setdefault(p.get("section","General"), []).append(p)
    secs = [s for s in ORDER if s in grouped] + [s for s in grouped if s not in ORDER]

    cards_html = ""
    for si, sec in enumerate(secs):
        rows = ""
        for p in grouped[sec]:
            desc_html = f'<p class="cd">{p.get("description","")}</p>' if include_descriptions and p.get("description") else ""
            tags_html = "".join(f'<span class="tag">{t}</span>' for t in p.get("tags",[]))
            rows += f'''
      <div class="card">
        <div class="ci"><img src="{p["b64"]}" alt="Photo {p["num"]}"/><span class="badge">#{p["num"]}</span></div>
        <div class="cb">
          <h3 class="ct">{p.get("title", f"Photo {p['num']}")}</h3>
          <div class="ct-line"></div>
          {desc_html}
          <div class="ctags">{tags_html}</div>
          <div class="area-tag">{sec}</div>
        </div>
      </div>'''
        cards_html += f'''
    <div class="sec">
      <div class="sl"><span class="sn">{str(si+1).zfill(2)}</span><span class="st">{sec}</span></div>
      <div class="grid">{rows}
      </div>
    </div>'''

    cover_b64 = photos[0]["b64"] if photos else ""
    fonts_css = build_fonts_css()
    serif  = "'DS',Georgia,'Times New Roman',serif"
    sans   = "'BS','Liberation Sans',Arial,sans-serif"

    LOGO = '<svg width="52" height="52" viewBox="0 0 80 80" fill="none"><polygon points="40,5 75,30 75,72 5,72 5,30" stroke="#C9A96E" stroke-width="3" fill="rgba(25,24,22,0.5)" stroke-linejoin="round"/><polyline points="18,30 18,62 62,62 62,30" stroke="#C9A96E" stroke-width="2.5" fill="none" stroke-linejoin="round"/><polyline points="30,62 30,42 50,42" stroke="#C9A96E" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/><line x1="30" y1="50" x2="46" y2="50" stroke="#C9A96E" stroke-width="2.5" stroke-linecap="round"/></svg>'

    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8">
<title>Before &amp; After — {address} | Formo Renovation</title>
<style>
{fonts_css}
*,*::before,*::after{{-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important;color-adjust:exact !important;box-sizing:border-box;margin:0;padding:0;}}
@page{{size:letter;margin:0;}}
html,body{{background:#191816 !important;color:#F8F4EF;font-family:{sans};font-weight:300;}}
.cover{{width:100%;height:100vh;position:relative;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;padding-bottom:60px;text-align:center;background:#191816 !important;page-break-after:always;overflow:hidden;}}
.cover-bg{{position:absolute;inset:0;background-size:cover;background-position:center top;filter:brightness(0.28) saturate(0.65);-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important;}}
.cover-ov{{position:absolute;inset:0;background:linear-gradient(to bottom,rgba(25,24,22,0.05) 0%,rgba(25,24,22,0.62) 38%,rgba(25,24,22,0.95) 70%,#191816 100%) !important;-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important;}}
.cc{{position:relative;z-index:2;display:flex;flex-direction:column;align-items:center;}}
.bn{{font-family:{sans};font-weight:700;font-size:22px;letter-spacing:.28em;color:#F8F4EF !important;margin-top:14px;text-transform:uppercase;}}
.bs{{font-size:10px;letter-spacing:.4em;color:#C9A96E !important;margin-top:3px;text-transform:uppercase;}}
.dv{{width:1px;height:44px;background:linear-gradient(to bottom,transparent,#C9A96E,transparent) !important;margin:18px auto;-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important;}}
.h1{{font-family:{serif};font-weight:300;font-size:56px;line-height:1.08;color:#fff !important;}}
.h1 em{{font-style:italic;color:#E2C98A !important;}}
.adr{{font-size:11px;letter-spacing:.26em;color:#C8BFB0 !important;text-transform:uppercase;margin-top:12px;}}
.stats{{display:flex;gap:44px;margin-top:36px;flex-wrap:wrap;justify-content:center;}}
.sv{{font-family:{serif};font-size:30px;font-weight:300;color:#E2C98A !important;display:block;line-height:1;}}
.sl2{{font-size:9px;letter-spacing:.22em;color:#7A7060 !important;text-transform:uppercase;margin-top:4px;display:block;}}
.tgl{{margin-top:32px;font-size:10px;letter-spacing:.24em;color:#7A7060 !important;text-transform:uppercase;display:flex;align-items:center;gap:12px;}}
.tgl::before,.tgl::after{{content:'';display:block;width:44px;height:1px;background:#9A7840 !important;-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important;}}
.band{{background:#C9A96E !important;padding:14px 36px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important;}}
.band p{{font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:#191816 !important;font-weight:700;}}
.wrap{{max-width:1080px;margin:0 auto;padding:0 28px;}}
.sec{{padding-top:48px;}}
.sl{{display:flex;align-items:center;gap:12px;padding-bottom:18px;border-bottom:1px solid rgba(201,169,110,0.2);}}
.sn{{font-family:{serif};font-size:10px;letter-spacing:.3em;color:#C9A96E !important;}}
.st{{font-family:{sans};font-size:17px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#F8F4EF !important;}}
.grid{{border:1px solid rgba(201,169,110,0.2);border-top:none;background:rgba(201,169,110,0.18) !important;-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important;}}
.card{{display:table;width:100%;background:#252220 !important;border-bottom:1px solid rgba(201,169,110,0.14);page-break-inside:avoid;break-inside:avoid;-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important;}}
.card:last-child{{border-bottom:none;}}
.ci{{display:table-cell;width:52%;vertical-align:top;position:relative;overflow:hidden;}}
.ci img{{width:100%;height:{'220px' if include_descriptions else '260px'};object-fit:cover;display:block;}}
.badge{{display:inline-block;position:absolute;top:10px;left:10px;background:rgba(25,24,22,.88) !important;border:1px solid #9A7840;color:#C9A96E !important;font-family:{sans};font-size:10px;font-weight:700;letter-spacing:.14em;padding:2px 8px;-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important;}}
.cb{{display:table-cell;width:48%;padding:20px 22px;vertical-align:middle;border-left:1px solid rgba(201,169,110,0.2);background:#252220 !important;-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important;}}
.ct{{font-family:{sans};font-size:14px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#F8F4EF !important;line-height:1.3;}}
.ct-line{{display:block;width:24px;height:2px;background:#C9A96E !important;margin:10px 0 {'10px' if include_descriptions else '0'};-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important;}}
.cd{{font-size:12px;color:#C8BFB0 !important;line-height:1.7;margin-bottom:10px;}}
.ctags{{display:flex;flex-wrap:wrap;gap:4px;margin-top:8px;}}
.tag{{font-size:8px;letter-spacing:.16em;text-transform:uppercase;color:#C9A96E !important;border:1px solid rgba(201,169,110,.3);padding:2px 7px;-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important;}}
.area-tag{{font-size:9px;letter-spacing:.2em;text-transform:uppercase;color:#7A7060 !important;margin-top:8px;}}
.summ{{padding:52px 0 44px;border-top:1px solid rgba(201,169,110,0.2);margin-top:48px;}}
.smtit{{font-family:{serif};font-size:34px;font-weight:300;color:#C9A96E !important;text-align:center;margin-bottom:28px;}}
.kpis{{display:table;width:100%;background:rgba(201,169,110,0.18) !important;border:1px solid rgba(201,169,110,0.2);-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important;}}
.kpi{{display:table-cell;width:33%;padding:22px;text-align:center;background:#252220 !important;border-right:1px solid rgba(201,169,110,0.2);-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important;}}
.kpi:last-child{{border-right:none;}}
.kv{{font-family:{serif};font-size:36px;font-weight:300;color:#E2C98A !important;line-height:1;display:block;}}
.kl{{font-size:9px;letter-spacing:.2em;text-transform:uppercase;color:#7A7060 !important;margin-top:5px;display:block;}}
footer{{background:#252220 !important;border-top:1px solid rgba(201,169,110,0.2);padding:24px 36px;display:table;width:100%;-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important;}}
.ft-l,.ft-r{{display:table-cell;vertical-align:middle;}}
.ft-r{{text-align:right;}}
.fb{{font-family:{sans};font-size:17px;font-weight:700;letter-spacing:.22em;color:#F8F4EF !important;}}
.fb span{{color:#C9A96E !important;}}
.fsub{{font-size:9px;letter-spacing:.2em;color:#7A7060 !important;text-transform:uppercase;margin-top:2px;}}
.fi{{font-size:10px;color:#7A7060 !important;line-height:1.8;}}
.fi strong{{color:#C8BFB0 !important;display:block;}}
</style></head><body>
<div class="cover">
  <div class="cover-bg" style="background-image:url('{cover_b64}')"></div>
  <div class="cover-ov"></div>
  <div class="cc">
    {LOGO}
    <div class="bn">FORMO</div><div class="bs">RENOVATION</div>
    <div class="dv"></div>
    <h1 class="h1">Before &amp; <em>After</em></h1>
    <p class="adr">{address} &middot; {project} &middot; {date}</p>
    <div class="stats">
      <div><span class="sv">{len(photos)}</span><span class="sl2">Photos</span></div>
      <div><span class="sv">{len(secs)}</span><span class="sl2">Work Areas</span></div>
      <div><span class="sv">100%</span><span class="sl2">Before &amp; After</span></div>
    </div>
    <div class="tgl">BUILT ON QUALITY &middot; DRIVEN BY INTEGRITY</div>
  </div>
</div>
<div class="band"><p>Full Renovation Report &bull; {address}</p><p>Formo Renovation &bull; {date}</p></div>
<div class="wrap">
{cards_html}
<div class="summ">
  <h2 class="smtit">Project Summary</h2>
  <div class="kpis">
    <div class="kpi"><span class="kv">{len(photos)}</span><span class="kl">Photos Documented</span></div>
    <div class="kpi"><span class="kv">{len(secs)}</span><span class="kl">Work Areas</span></div>
    <div class="kpi"><span class="kv">100%</span><span class="kl">Scope Coverage</span></div>
  </div>
</div>
</div>
<footer>
  <div class="ft-l"><div class="fb">FORMO <span>RENOVATION</span></div><div class="fsub">Built on Quality &middot; Driven by Integrity</div></div>
  <div class="ft-r"><div class="fi"><strong>{date}</strong>{project} &mdash; {address}<br>Formo Renovation</div></div>
</footer>
</body></html>"""


# ── Routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/generate", methods=["POST"])
def generate():
    if "pdf" not in request.files:
        return jsonify({"error": "No PDF uploaded"}), 400

    pdf_file = request.files["pdf"]
    mode = request.form.get("mode", "client")  # "client" or "internal"
    include_descriptions = (mode == "internal") and bool(ANTHROPIC_KEY)

    with tempfile.TemporaryDirectory() as tmp:
        # Save uploaded PDF
        pdf_path = os.path.join(tmp, secure_filename(pdf_file.filename or "report.pdf"))
        pdf_file.save(pdf_path)

        # Extract metadata
        meta = extract_meta(pdf_path)

        # Extract images
        try:
            imgs = extract_images(pdf_path, tmp)
        except Exception as e:
            return jsonify({"error": f"Could not extract images: {str(e)}"}), 500

        if len(imgs) < 2:
            return jsonify({"error": "No photos found. Make sure this is a CompanyCam Before & After report."}), 400

        cover_img = imgs[0]
        photo_imgs = imgs[1:]

        # Build photo data
        photos = []
        for i, img_path in enumerate(photo_imgs, 1):
            p = {"num": i, "b64": img_to_b64(img_path)}
            if include_descriptions:
                cap = ai_describe(img_path, i)
                p.update(cap)
            else:
                p.update({"section": "General", "title": f"Photo {i}", "description": "", "tags": []})
            photos.append(p)

        # Add cover as first photo b64 for template
        photos_with_cover = [{"num": 0, "b64": img_to_b64(cover_img)}] + photos

        # Build HTML
        html = build_html(meta, photos_with_cover[1:], include_descriptions)
        # Use cover separately
        html = html  # already handled in build_html

        # Convert to PDF
        html_path = os.path.join(tmp, "report.html")
        with open(html_path, "w") as f:
            f.write(html)

        out_pdf = os.path.join(tmp, "report.pdf")
        result = subprocess.run([
            "wkhtmltopdf",
            "--enable-local-file-access",
            "--background",
            "--no-stop-slow-scripts",
            "--page-size", "Letter",
            "--margin-top", "0",
            "--margin-bottom", "0",
            "--margin-left", "0",
            "--margin-right", "0",
            "--zoom", "1.0",
            "--disable-external-links",
            html_path, out_pdf
        ], capture_output=True)

        if not os.path.exists(out_pdf):
            return jsonify({"error": "PDF generation failed"}), 500

        # Build filename
        addr = meta.get("address", "Report").replace(" ", "_")
        suffix = "_Internal" if include_descriptions else "_Client"
        filename = f"Formo_{addr}{suffix}.pdf"

        return send_file(
            out_pdf,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
