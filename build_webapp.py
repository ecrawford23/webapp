#!/usr/bin/env python3
"""Build the WEB (Vercel) version of the Command Center.

Reuses the locally-built Evie_Command_Center.html (which already includes
the ADHD day planner, open-by-default tasks, and done-task collapsing).
Swaps ONLY the persistence layer:
  - localStorage  ->  a password-gated serverless API (/api/state)
  - adds a password gate overlay + a "Saved" indicator
  - checkmarks/notes now live in a backend store, so they sync across
    devices AND survive every morning rebuild/redeploy.

Run order each morning:
    python3 build_command_center.py     # rebuilds Evie_Command_Center.html from tasks.json
    python3 webapp/build_webapp.py       # regenerates webapp/public/index.html
Then deploy webapp/ to Vercel (Git push or `vercel --prod`).
"""
import pathlib, sys

BASE = pathlib.Path(__file__).resolve().parent
SRC = BASE.parent / "Evie_Command_Center.html"
OUT_DIR = BASE / "public"

if not SRC.exists():
    sys.exit("Source not found: %s — run build_command_center.py first." % SRC)

html = SRC.read_text(encoding="utf-8")

# --- 1. State now starts empty (loaded from the API at boot) ---
LOAD_OLD = 'let state=JSON.parse(localStorage.getItem(KEY)||"{}");'
LOAD_NEW = 'let state={};  /* loaded from /api/state at boot */'
assert LOAD_OLD in html, "state load line not found — did the build template change?"
html = html.replace(LOAD_OLD, LOAD_NEW)

# --- 2. save() now debounce-POSTs to the API; plus auth/load/boot helpers ---
SAVE_OLD = 'function save(){ localStorage.setItem(KEY, JSON.stringify(state)); }'
SAVE_NEW = r'''const API="/api/state";
function getPw(){ try{ return sessionStorage.getItem("cc_pw")||""; }catch(e){ return ""; } }
let _saveTimer=null, _dirty=false;
function save(){ _dirty=true; setSaved("saving"); clearTimeout(_saveTimer); _saveTimer=setTimeout(flush,600); }
async function flush(){ if(!_dirty) return; _dirty=false;
  try{ const r=await fetch(API,{method:"POST",headers:{"content-type":"application/json","x-cc-password":getPw()},body:JSON.stringify({state:state})});
       if(!r.ok) throw new Error(r.status); setSaved("ok"); }
  catch(e){ _dirty=true; setSaved("err"); } }
function setSaved(kind){ const el=document.getElementById("savep"); if(!el)return;
  if(kind==="saving"){ el.textContent="Saving…"; el.style.background="#7a6a1f"; }
  else if(kind==="ok"){ el.textContent="Saved ✓"; el.style.background="#16331f"; }
  else { el.textContent="Save failed — will retry"; el.style.background="#7a1f1f"; } }
window.addEventListener("beforeunload",function(){ if(_dirty&&navigator.sendBeacon){
  navigator.sendBeacon(API, new Blob([JSON.stringify({state:state,pw:getPw()})],{type:"application/json"})); } });
async function loadState(){ const r=await fetch(API,{headers:{"x-cc-password":getPw()}});
  if(r.status===401){ const e=new Error("auth"); e.auth=true; throw e; }
  if(!r.ok) throw new Error(r.status); const d=await r.json(); state=d.state||{}; }
async function boot(){ try{ await loadState(); const g=document.getElementById("gate"); if(g)g.style.display="none"; render(); }
  catch(e){ const g=document.getElementById("gate"); if(g)g.style.display="flex";
    const m=document.getElementById("gatemsg"); if(m) m.textContent = e&&e.auth ? "Wrong password — try again." : "Couldn't reach the server — try again."; } }
function submitPw(){ const v=document.getElementById("pwin").value; try{ sessionStorage.setItem("cc_pw",v); }catch(e){} boot(); }'''
assert SAVE_OLD in html, "save() line not found — did the build template change?"
html = html.replace(SAVE_OLD, SAVE_NEW)

# --- 3. Replace the standalone bootstrap render() with the gated boot ---
BOOT_OLD = '\nrender();\n</script>'
BOOT_NEW = ('\nif(getPw()){ boot(); } else { var _g=document.getElementById("gate"); if(_g)_g.style.display="flex"; '
            'setTimeout(function(){ var e=document.getElementById("pwin"); if(e)e.focus(); },40); }\n</script>')
assert BOOT_OLD in html, "bootstrap render() not found"
html = html.replace(BOOT_OLD, BOOT_NEW)

# --- 4. Inject the password gate overlay + Saved pill just before <script> ---
GATE = '''<div id="gate" style="display:none;position:fixed;inset:0;background:#1f2a37;z-index:99999;align-items:center;justify-content:center;flex-direction:column;font-family:system-ui,-apple-system,Segoe UI,sans-serif">
  <div style="background:#fff;padding:30px 28px;border-radius:14px;max-width:330px;width:88%;text-align:center;box-shadow:0 16px 50px rgba(0,0,0,.35)">
    <div style="font-weight:700;font-size:20px;letter-spacing:.14em;color:#1f2a37">BELLAMARE</div>
    <div style="color:#777;font-size:13px;margin:4px 0 18px">Command Center — private</div>
    <input id="pwin" type="password" placeholder="Password" onkeydown="if(event.key==='Enter')submitPw()" style="width:100%;padding:11px 13px;border:1px solid #ccc;border-radius:9px;font-size:15px;box-sizing:border-box">
    <div id="gatemsg" style="color:#b00020;font-size:12px;min-height:16px;margin:9px 0"></div>
    <button onclick="submitPw()" style="width:100%;padding:11px;border:0;border-radius:9px;background:#1f2a37;color:#fff;font-size:15px;font-weight:600;cursor:pointer">Unlock</button>
  </div>
</div>
<div id="savep" style="position:fixed;bottom:14px;right:14px;background:#16331f;color:#fff;padding:6px 13px;border-radius:20px;font-size:12px;font-family:system-ui,sans-serif;opacity:.92;z-index:9000">Saved ✓</div>
'''
html = html.replace('<script>', GATE + '<script>', 1)

# --- 5 removed: ADHD planner is now baked into build_command_center.py ---
# The base HTML already has the day planner, open-by-default tasks, and done-task section.

OUT_DIR.mkdir(parents=True, exist_ok=True)
(OUT_DIR / "index.html").write_text(html, encoding="utf-8")
print("Wrote", OUT_DIR / "index.html", "(%d bytes)" % len((OUT_DIR/"index.html").read_text()))
