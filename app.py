import os, base64, subprocess, tempfile, re, json
from flask import Flask, request, jsonify, render_template, Response
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

def extract_images(pdf_path, out_dir):
    prefix = os.path.join(out_dir, "img")
    subprocess.run(["pdfimages", "-j", pdf_path, prefix], check=True, capture_output=True)
    imgs = sorted(
        [os.path.join(out_dir, f) for f in os.listdir(out_dir)
         if re.match(r"img-\d+\.jpe?g$", f, re.IGNORECASE)],
        key=lambda p: int(re.search(r"(\d+)", os.path.basename(p)).group(1))
    )
    return imgs

def extract_meta(pdf_path):
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
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()

def ai_describe(img_path, num):
    if not ANTHROPIC_KEY:
        return {"section": "General", "title": "Photo " + str(num), "description": "", "tags": []}
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=180,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                {"type": "text", "text":
                    "Before/after renovation photo #" + str(num) + ". BEFORE=left, AFTER=right.\n"
                    "Reply ONLY valid JSON:\n"
                    '{"section":"<Exterior|Deck|Doors|Flooring|Bathrooms|Kitchen|Paint & Drywall|Windows & Lighting|Trim & Molding|Utilities|General>",'
                    '"title":"<4-6 word English title>",'
                    '"description":"<EXACTLY 2 short English sentences. First: problem before. Second: what was done. Max 18 words each.>",'
                    '"tags":["<tag1>","<tag2>"]}'}
            ]}]
        )
        text = msg.content[0].text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception:
        return {"section": "General", "title": "Photo " + str(num), "description": "Renovation work completed.", "tags": []}

LOGO = '<img src="https://raw.https://github.com/formorenovation-a11y/Formo-report-generatorv1/blob/main/logo%20new.png" style="height:64px;margin-bottom:16px;object-fit:contain;" alt="Formo Renovation"/>'

def build_html(meta, cover_b64, photos, include_descriptions):
    address = meta.get("address", "")
    project = meta.get("project", "")
    date    = meta.get("date", "")

    ORDER = ["Exterior","Deck","Doors","Flooring","Bathrooms","Kitchen",
             "Paint & Drywall","Windows & Lighting","Trim & Molding","Utilities","General"]
    grouped = {}
    for p in photos:
        grouped.setdefault(p.get("section","General"), []).append(p)
    secs = [s for s in ORDER if s in grouped] + [s for s in grouped if s not in ORDER]

    cards = ""
    for si, sec in enumerate(secs):
        rows = ""
        for p in grouped[sec]:
            desc = ('<p class="cd">' + p.get("description","") + "</p>") if include_descriptions and p.get("description") else ""
            tags = "".join('<span class="tag">' + t + "</span>" for t in p.get("tags",[]))
            num  = str(p["num"])
            title = p.get("title","Photo " + num)
            rows += (
                '<div class="card">'
                '<div class="ci"><img src="' + p["b64"] + '" loading="lazy"/>'
                '<div class="badge">#' + num + '</div></div>'
                '<div class="cb">'
                '<h3 class="ct">' + title + '</h3>'
                '<div class="ct-line"></div>'
                + desc +
                '<div class="ctags">' + tags + '</div>'
                '<div class="area-tag">' + sec + '</div>'
                '</div></div>'
            )
        cards += (
            '<div class="sec">'
            '<div class="sl"><span class="sn">' + str(si+1).zfill(2) + '</span>'
            '<span class="st">' + sec + '</span></div>'
            '<div class="grid">' + rows + '</div>'
            '</div>'
        )

    n_photos = str(len(photos))
    n_secs   = str(len(secs))

    return (
        '<!DOCTYPE html><html lang="en"><head>'
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Before &amp; After \u2014 ' + address + ' | Formo Renovation</title>'
        '<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;1,300;1,400&family=Barlow:wght@300;400;500;600&family=Barlow+Condensed:wght@400;600;700&display=swap" rel="stylesheet">'
        '<style>'
        ':root{--g:#C9A96E;--gl:#E2C98A;--gd:#9A7840;--b:#191816;--b2:#252220;--c:#F8F4EF;--c2:#C8BFB0;--m:#7A7060;--bd:rgba(201,169,110,0.16);}'
        '*{margin:0;padding:0;box-sizing:border-box;}'
        'body{background:var(--b);color:var(--c);font-family:"Barlow",sans-serif;font-weight:300;line-height:1.6;}'
        '.cover{position:relative;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;overflow:hidden;padding-bottom:72px;text-align:center;}'
        '.cbg{position:absolute;inset:0;background-size:cover;background-position:center top;filter:brightness(0.28) saturate(0.7);transform:scale(1.04);}'
        '.cov{position:absolute;inset:0;background:linear-gradient(to bottom,rgba(25,24,22,0.1) 0%,rgba(25,24,22,0.6) 40%,rgba(25,24,22,0.94) 72%,#191816 100%);}'
        '.cc{position:relative;z-index:2;display:flex;flex-direction:column;align-items:center;}'
        '.brd{font-family:"Barlow Condensed",sans-serif;font-weight:700;font-size:26px;letter-spacing:.28em;color:var(--c);}'
        '.bsb{font-size:11px;letter-spacing:.4em;color:var(--g);}'
        '.rl{width:1px;height:52px;background:linear-gradient(to bottom,transparent,var(--g),transparent);margin:22px auto;}'
        '.h1{font-family:"Cormorant Garamond",serif;font-size:clamp(46px,8vw,80px);font-weight:300;line-height:1.04;color:#fff;}'
        '.h1 em{font-style:italic;color:var(--gl);}'
        '.adr{font-size:12px;letter-spacing:.28em;color:var(--c2);text-transform:uppercase;margin-top:14px;}'
        '.stats{display:flex;gap:48px;margin-top:44px;flex-wrap:wrap;justify-content:center;}'
        '.sv{font-family:"Cormorant Garamond",serif;font-size:36px;font-weight:300;color:var(--gl);display:block;line-height:1;}'
        '.slb{font-size:10px;letter-spacing:.22em;color:var(--m);text-transform:uppercase;margin-top:5px;display:block;}'
        '.tl{margin-top:40px;font-size:11px;letter-spacing:.25em;color:var(--m);text-transform:uppercase;display:flex;align-items:center;gap:14px;}'
        '.tl::before,.tl::after{content:"";display:block;width:56px;height:1px;background:var(--gd);opacity:.6;}'
        '.band{background:var(--g);padding:17px 40px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;}'
        '.band p{font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:#191816;font-weight:600;}'
        '.wrap{max-width:1120px;margin:0 auto;padding:0 32px;}'
        '.sec{padding-top:68px;}'
        '.sl{display:flex;align-items:center;gap:14px;padding-bottom:28px;border-bottom:1px solid var(--bd);}'
        '.sn{font-family:"Cormorant Garamond",serif;font-size:11px;letter-spacing:.3em;color:var(--g);}'
        '.st{font-family:"Barlow Condensed",sans-serif;font-size:19px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;}'
        '.grid{display:grid;grid-template-columns:1fr;gap:1px;background:var(--bd);border:1px solid var(--bd);border-top:none;}'
        '.card{display:grid;grid-template-columns:1fr 1fr;background:var(--b2);transition:background .2s;}'
        '.card:hover{background:#2d2a26;}'
        '.ci{position:relative;overflow:hidden;aspect-ratio:1;}'
        '.ci img{width:100%;height:100%;object-fit:cover;display:block;transition:transform .5s;}'
        '.card:hover .ci img{transform:scale(1.03);}'
        '.badge{position:absolute;top:10px;left:10px;background:rgba(25,24,22,.82);border:1px solid var(--gd);color:var(--g);font-family:"Barlow Condensed",sans-serif;font-size:11px;letter-spacing:.15em;padding:3px 9px;border-radius:1px;}'
        '.cb{padding:28px 24px;display:flex;flex-direction:column;justify-content:center;border-left:1px solid var(--bd);}'
        '.ct{font-family:"Barlow Condensed",sans-serif;font-size:17px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--c);margin-bottom:10px;}'
        '.ct-line{display:block;width:28px;height:1px;background:var(--g);margin-bottom:10px;}'
        '.cd{font-size:13.5px;color:var(--c2);line-height:1.75;margin-bottom:10px;}'
        '.ctags{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px;}'
        '.tag{font-size:9px;letter-spacing:.18em;text-transform:uppercase;color:var(--g);border:1px solid rgba(201,169,110,.28);padding:3px 9px;border-radius:1px;}'
        '.area-tag{font-size:9px;letter-spacing:.2em;text-transform:uppercase;color:var(--m);margin-top:10px;}'
        '.summ{padding:72px 0 56px;border-top:1px solid var(--bd);margin-top:68px;}'
        '.smtit{font-family:"Cormorant Garamond",serif;font-size:40px;font-weight:300;color:var(--g);text-align:center;margin-bottom:36px;}'
        '.kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--bd);border:1px solid var(--bd);}'
        '.kpi{background:var(--b2);padding:26px;text-align:center;}'
        '.kv{font-family:"Cormorant Garamond",serif;font-size:44px;font-weight:300;color:var(--gl);line-height:1;}'
        '.kl{font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--m);margin-top:6px;display:block;}'
        'footer{background:var(--b2);border-top:1px solid var(--bd);padding:32px 40px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px;}'
        '.fb{font-family:"Barlow Condensed",sans-serif;font-size:19px;font-weight:700;letter-spacing:.22em;}'
        '.fb span{color:var(--g);}'
        '.fsub{font-size:10px;letter-spacing:.2em;color:var(--m);text-transform:uppercase;margin-top:3px;}'
        '.fi{text-align:right;font-size:11px;color:var(--m);line-height:1.8;}'
        '.fi strong{color:var(--c2);display:block;}'
        '@keyframes fadeUp{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:translateY(0)}}'
        '.cc>*{animation:fadeUp .9s ease both;}'
        '.cc>*:nth-child(1){animation-delay:.1s}.cc>*:nth-child(2){animation-delay:.25s}'
        '.cc>*:nth-child(3){animation-delay:.35s}.cc>*:nth-child(4){animation-delay:.44s}'
        '.cc>*:nth-child(5){animation-delay:.52s}.cc>*:nth-child(6){animation-delay:.6s}'
        '@media(max-width:700px){.card{grid-template-columns:1fr}.cb{border-left:none;border-top:1px solid var(--bd)}.kpis{grid-template-columns:1fr 1fr}.wrap{padding:0 16px}.fi{text-align:left}}'
        '</style></head><body>'
        '<section class="cover">'
        '<div class="cbg" style="background-image:url(\'' + cover_b64 + '\')"></div>'
        '<div class="cov"></div>'
        '<div class="cc">'
        + LOGO +
        '<div class="brd">FORMO</div><div class="bsb">RENOVATION</div>'
        '<div class="rl"></div>'
        '<h1 class="h1">Before &amp; <em>After</em></h1>'
        '<p class="adr">' + address + ' &middot; ' + project + ' &middot; ' + date + '</p>'
        '<div class="stats">'
        '<div><span class="sv">' + n_photos + '</span><span class="slb">Photos</span></div>'
        '<div><span class="sv">' + n_secs + '</span><span class="slb">Work Areas</span></div>'
        '<div><span class="sv">100%</span><span class="slb">Before &amp; After</span></div>'
        '</div>'
        '<div class="tl">BUILT ON QUALITY &middot; DRIVEN BY INTEGRITY</div>'
        '</div></section>'
        '<div class="band"><p>Full Renovation Report &bull; ' + address + '</p><p>Formo Renovation &bull; ' + date + '</p></div>'
        '<div class="wrap">'
        + cards +
        '<div class="summ"><h2 class="smtit">Project Summary</h2>'
        '<div class="kpis">'
        '<div class="kpi"><div class="kv">' + n_photos + '</div><span class="kl">Photos Documented</span></div>'
        '<div class="kpi"><div class="kv">' + n_secs + '</div><span class="kl">Work Areas</span></div>'
        '<div class="kpi"><div class="kv">100%</div><span class="kl">Scope Coverage</span></div>'
        '</div></div>'
        '</div>'
        '<footer>'
        '<div><div class="fb">FORMO <span>RENOVATION</span></div><div class="fsub">Built on Quality &middot; Driven by Integrity</div></div>'
        '<div class="fi"><strong>' + date + '</strong>' + project + ' &mdash; ' + address + '<br>Formo Renovation</div>'
        '</footer>'
        '</body></html>'
    )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    if "pdf" not in request.files:
        return jsonify({"error": "No PDF uploaded"}), 400

    pdf_file = request.files["pdf"]
    mode = request.form.get("mode", "client")
    include_descriptions = (mode == "internal") and bool(ANTHROPIC_KEY)

    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = os.path.join(tmp, secure_filename(pdf_file.filename or "report.pdf"))
        pdf_file.save(pdf_path)

        meta = extract_meta(pdf_path)

        try:
            imgs = extract_images(pdf_path, tmp)
        except Exception as e:
            return jsonify({"error": "Could not extract images: " + str(e)}), 500

        if len(imgs) < 2:
            return jsonify({"error": "No photos found. Make sure this is a CompanyCam Before & After report."}), 400

        cover_b64  = img_to_b64(imgs[0])
        photo_imgs = imgs[1:]

        photos = []
        for i, img_path in enumerate(photo_imgs, 1):
            p = {"num": i, "b64": img_to_b64(img_path)}
            if include_descriptions:
                p.update(ai_describe(img_path, i))
            else:
                p.update({"section": "General", "title": "Photo " + str(i),
                          "description": "", "tags": []})
            photos.append(p)

        html = build_html(meta, cover_b64, photos, include_descriptions)

        addr = meta.get("address", "Report").replace(" ", "_")
        suffix = "_Internal" if include_descriptions else "_Client"
        filename = "Formo_" + addr + suffix + ".html"

        return Response(
            html,
            mimetype="text/html",
            headers={"Content-Disposition": 'attachment; filename="' + filename + '"'}
        )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
