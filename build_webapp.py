#!/usr/bin/env python3
"""Build the WEB (Vercel) version of the Command Center.

Reuses the locally-built Evie_Command_Center.html for all styling/markup,
and swaps ONLY the persistence layer:
  - localStorage  ->  a password-gated serverless API (/api/state)
  - adds a password gate overlay + a "Saved" indicator
  - checkmarks/notes now live in a backend store, so they sync across
    devices AND survive every morning rebuild/redeploy.

Run order each morning (after the normal build):
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

# --- 5. ADHD planner layer: day-at-a-glance (9–4), step date chips, calm overview ---
ADHD_CSS = '''<style id="adhdcss">
.now{display:none!important;}
#dayplan{margin:16px 0 10px;font-family:inherit}
#dayplan .one{background:var(--navy,#1f2a37);color:#fff;border-radius:14px;padding:16px 18px;margin-bottom:14px;box-shadow:0 4px 18px rgba(0,0,0,.12)}
#dayplan .one .lbl{font-size:11px;letter-spacing:.16em;text-transform:uppercase;opacity:.72}
#dayplan .one .ttl{font-size:19px;font-weight:700;margin:5px 0 3px;line-height:1.2}
#dayplan .one .stp{font-size:14px;opacity:.92}
#dayplan .one button{margin-top:11px;border:0;border-radius:9px;background:#fff;color:var(--navy,#1f2a37);font-weight:700;padding:8px 14px;cursor:pointer;font-size:13px}
#dayplan h3{font-size:12px;letter-spacing:.13em;text-transform:uppercase;color:var(--navy,#1f2a37);opacity:.7;margin:16px 0 8px}
#dayplan .planwrap{display:flex;flex-direction:column;gap:8px}
.tblock{display:flex;gap:12px;align-items:center;padding:9px 12px;border:1px solid rgba(0,0,0,.08);border-radius:11px;background:#fff}
.tblock .tt{min-width:62px;font-variant-numeric:tabular-nums;font-weight:700;color:var(--navy,#1f2a37);font-size:13px}
.tblock .bd{flex:1}
.tblock .bd .tk{font-weight:600;font-size:14px}
.tblock .bd .sp{font-size:13px;color:#5a5a5a;margin-top:1px}
.tblock .done{border:0;background:var(--green,#2e7d32);color:#fff;border-radius:8px;padding:6px 11px;cursor:pointer;font-size:13px}
.tblock.lunch{justify-content:center;color:#8a7f63;font-style:italic;background:#faf7ef;border-style:dashed}
.tblock.od .tt{color:#b00020}
.later .tblock{opacity:.72}
.wk{display:flex;flex-wrap:wrap;gap:7px}
.wk .wki{font-size:12px;border:1px solid rgba(0,0,0,.1);border-radius:20px;padding:4px 11px;background:#fff}
.wk .wki b{color:var(--navy,#1f2a37)}
.waitlist{font-size:12.5px;color:#777;line-height:1.6}
.stepdate{display:inline-block;margin-left:8px;font-size:10.5px;letter-spacing:.03em;color:#7a6a1f;background:#f4ecd0;border-radius:10px;padding:1px 7px;vertical-align:middle;white-space:nowrap}
.stepdate.td{color:#fff;background:var(--green,#2e7d32)}
</style>'''
html = html.replace('<div class="now" id="now"></div>',
                    '<div class="now" id="now"></div>\n  <section id="dayplan"></section>\n  ' + ADHD_CSS)

ADHD_JS = r'''
/* ===== ADHD planner layer ===== */
const DAY_START=540, DAY_END=960, LUNCH_START=720, LUNCH_MIN=30; /* 9:00–16:00, lunch 30m */
const MONTHS={jan:0,feb:1,mar:2,apr:3,may:4,jun:5,jul:6,aug:7,sep:8,oct:9,nov:10,dec:11};
function adhdEsc(s){ return (s||"").replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function today0(){ const d=new Date(); d.setHours(0,0,0,0); return d; }
function sameDay(a,b){ return a&&b&&a.getFullYear()===b.getFullYear()&&a.getMonth()===b.getMonth()&&a.getDate()===b.getDate(); }
function parseDueDate(t){
  const w=t.when||""; const T=today0();
  if(/\btoday\b/i.test(w)) return new Date(T);
  if(/\btomorrow\b/i.test(w)){ const d=new Date(T); d.setDate(d.getDate()+1); return d; }
  const re=/(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2})/gi; let m, dates=[];
  while((m=re.exec(w))){ const mon=MONTHS[m[1].slice(0,3).toLowerCase()]; const day=parseInt(m[2],10);
    if(mon==null||day<1||day>31) continue; let d=new Date(T.getFullYear(),mon,day);
    if((T-d)/864e5>180) d=new Date(T.getFullYear()+1,mon,day); dates.push(d); }
  if(!dates.length) return null;
  const future=dates.filter(d=>d>=T).sort((a,b)=>a-b);
  return future.length?future[0]:dates.sort((a,b)=>b-a)[0];
}
function isParked(t){ return /\b(parked|on hold)\b/i.test(t.when||""); }
function bizDays(a,b){ const out=[]; const d=new Date(a); while(d<=b){ const wd=d.getDay(); if(wd!==0&&wd!==6) out.push(new Date(d)); d.setDate(d.getDate()+1);} return out; }
function fmtChip(d){ const T=today0(); const diff=Math.round((d-T)/864e5);
  if(diff===0) return "Today"; if(diff===1) return "Tomorrow";
  return d.toLocaleDateString(undefined,{weekday:"short",month:"short",day:"numeric"}); }
function fmtTime(mins){ let h=Math.floor(mins/60), m=mins%60, ap=h>=12?"pm":"am", hh=h%12; if(hh===0)hh=12; return hh+(m?(":"+(m<10?"0":"")+m):"")+ap; }
function durFor(t){ if(t.quick) return 20; return /Deck|Web|Vision|Deliverable|Brand|Dev|Event|Proposal/.test(t.type)?75:50; }
function stepSchedule(t){ const map={}; let due=parseDueDate(t);
  const rem=[]; t.steps.forEach((_,i)=>{ if(!stepDone(t.id,i)) rem.push(i); });
  if(!rem.length||!due) return map; const T=today0(); let dueD=new Date(due); if(dueD<T) dueD=new Date(T);
  let days=bizDays(T,dueD); if(!days.length) days=[new Date(T)];
  const n=rem.length,k=days.length;
  rem.forEach((si,idx)=>{ map[si]=days[Math.min(k-1,Math.floor(idx*k/n))]; });
  map[rem[n-1]]=days[k-1]; return map;
}
function rankKey(t){ const due=parseDueDate(t),T=today0(); let bucket=2;
  if(due){ const diff=Math.round((due-T)/864e5); if(diff>=0&&diff<=1) bucket=0; else if(diff<0||t.od) bucket=1; else bucket=2; }
  else if(t.od) bucket=1; return [bucket, ORDER[t.pri], due?due.getTime():9e15]; }
function planToday(){ const T=today0(); let blocks=[], waiting=[];
  TASKS.forEach(t=>{ if(isDone(t)||isParked(t)) return; const ni=nextStepOf(t); if(ni<0) return;
    const stepTxt=t.steps[ni]||""; const blocked=/^(wait|waiting|hold|blocked)\b/i.test(stepTxt);
    const sched=stepSchedule(t); const sd=sched[ni];
    const dueNow=t.od||(sd&&sameDay(sd,T)); const urgent=t.pri==='urgent';
    if(blocked){ if(dueNow||urgent) waiting.push({t,ni,stepTxt}); return; }
    if(dueNow||urgent) blocks.push({t,ni,stepTxt}); });
  blocks.sort((a,b)=>{ const ka=rankKey(a.t),kb=rankKey(b.t); for(let i=0;i<3;i++){ if(ka[i]!==kb[i]) return ka[i]-kb[i]; } return 0; });
  return {blocks,waiting};
}
function weekMap(){ const T=today0(); const end=new Date(T); end.setDate(end.getDate()+7);
  return TASKS.filter(t=>!isDone(t)&&!isParked(t)).map(t=>({t,d:parseDueDate(t)}))
    .filter(x=>x.d&&x.d>=T&&x.d<=end).sort((a,b)=>a.d-b.d); }
function renderDayPlan(){ const host=document.getElementById('dayplan'); if(!host) return;
  const {blocks,waiting}=planToday(); let cur=DAY_START,lunchDone=false; const sched=[],later=[];
  for(const b of blocks){ if(!lunchDone&&cur>=LUNCH_START){ sched.push({lunch:1,start:cur}); cur+=LUNCH_MIN; lunchDone=true; }
    const d=durFor(b.t); if(cur+d>DAY_END){ later.push(b); continue; } sched.push(Object.assign({},b,{start:cur})); cur+=d; }
  let html=''; const first=sched.find(x=>!x.lunch);
  if(first){ html+='<div class="one"><div class="lbl">▶ The one thing</div><div class="ttl">'+adhdEsc(first.t.title)+'</div><div class="stp">'+adhdEsc(first.stepTxt)+'</div><button onclick="toggleStep(\''+first.t.id+'\','+first.ni+')">✓ Did this</button></div>'; }
  else { html+='<div class="one"><div class="lbl">▶ Today</div><div class="ttl">Nothing scheduled 🎉</div><div class="stp">Pick a ⚡ quick win below when you’re ready.</div></div>'; }
  html+='<h3>📅 Today · 9–4</h3><div class="planwrap">';
  if(sched.length){ sched.forEach(x=>{ if(x.lunch){ html+='<div class="tblock lunch">🍽 Lunch · '+fmtTime(x.start)+'</div>'; return; }
    html+='<div class="tblock'+(x.t.od?' od':'')+'"><div class="tt">'+fmtTime(x.start)+'</div><div class="bd"><div class="tk">'+adhdEsc(x.t.title)+(x.t.od?' <span style="color:#b00020">· overdue</span>':'')+'</div><div class="sp">'+adhdEsc(x.stepTxt)+'</div></div><button class="done" onclick="toggleStep(\''+x.t.id+'\','+x.ni+')">✓</button></div>'; }); }
  else { html+='<div class="tblock lunch">Clear day — breathe.</div>'; }
  html+='</div>';
  if(later.length){ html+='<h3>↪ If there’s time</h3><div class="planwrap later">';
    later.forEach(b=>{ html+='<div class="tblock"><div class="tt">later</div><div class="bd"><div class="tk">'+adhdEsc(b.t.title)+'</div><div class="sp">'+adhdEsc(b.stepTxt)+'</div></div><button class="done" onclick="toggleStep(\''+b.t.id+'\','+b.ni+')">✓</button></div>'; }); html+='</div>'; }
  if(waiting.length){ html+='<h3>⏸ Waiting on someone (not your move)</h3><div class="waitlist">';
    waiting.forEach(b=>{ html+='• <b>'+adhdEsc(b.t.title)+'</b> — '+adhdEsc(b.stepTxt)+'<br>'; }); html+='</div>'; }
  const wk=weekMap(); if(wk.length){ html+='<h3>🗓 This week</h3><div class="wk">';
    wk.forEach(x=>{ html+='<span class="wki"><b>'+fmtChip(x.d)+'</b> · '+adhdEsc(x.t.title)+'</span>'; }); html+='</div>'; }
  host.innerHTML=html;
}
function enhanceSteps(){ document.querySelectorAll('#board .steplist').forEach(ul=>{
  const cb=ul.querySelector('input.scb'); if(!cb) return; const m=(cb.getAttribute('onchange')||"").match(/toggleStep\('([^']+)'/); if(!m) return;
  const t=TASKS.find(x=>x.id===m[1]); if(!t) return; const sched=stepSchedule(t);
  ul.querySelectorAll('li').forEach(li=>{ const c=li.querySelector('input.scb'); if(!c) return;
    const mm=(c.getAttribute('onchange')||"").match(/,(\d+)\)/); if(!mm) return; const i=parseInt(mm[1],10);
    if(li.querySelector('.stepdate')||stepDone(t.id,i)) return; const d=sched[i]; if(!d) return;
    const chip=document.createElement('span'); chip.className='stepdate'+(sameDay(d,today0())?' td':''); chip.textContent=fmtChip(d); li.appendChild(chip); }); }); }
if(typeof render==='function'){ const _r=render; render=function(){ _r.apply(this,arguments); try{renderDayPlan();}catch(e){} try{enhanceSteps();}catch(e){} }; }
'''
html = html.replace('if(getPw()){ boot();', ADHD_JS + '\nif(getPw()){ boot();', 1)

OUT_DIR.mkdir(parents=True, exist_ok=True)
(OUT_DIR / "index.html").write_text(html, encoding="utf-8")
print("Wrote", OUT_DIR / "index.html", "(%d bytes)" % len((OUT_DIR/"index.html").read_text()))
