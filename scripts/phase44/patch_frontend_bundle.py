"""PHASE_44 patch: make the shipped frontend bundle follow runtime configuration.

The frontend source project is not part of this repository (only built assets
are), so the built bundle is patched in place. A byte-identical backup of the
pre-edit bundle and index.html is kept under ``frontend/backup/phase44_pre_edit``
and pre-edit SHA-256 hashes are recorded in
``reports/phase44_bundle_manifest.json`` before this script runs.

Two defects are repaired (health audit B4/B6, P0-4/P1-1):

1. Hardcoded API base ``http://localhost:8000``. The bundle now resolves the
   base from ``window.SAFEROUTE_API_BASE_URL`` (served by /runtime-config.js,
   empty by default = same origin) and falls back to ``location.origin``, so
   the UI follows whatever host/port serves it (8000, 8765, ...).

2. Hardcoded ~23-city suggestion list. The origin/destination combobox now
   debounces a live ``POST /api/geocode`` (Nominatim via the backend) and
   prefers real backend candidates; the bundled presets remain as the offline
   fallback whenever the backend/geocoder is unavailable.

No risk formulas, thresholds, route rendering or honesty logic are touched.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "frontend" / "assets" / "index-CXsvefbt.js"
BACKUP = ROOT / "frontend" / "backup" / "phase44_pre_edit" / "index-CXsvefbt.js"

# ---------------------------------------------------------------- Patch 1 --
OLD_Z2 = b"var Z2=`http://localhost:8000`"
NEW_Z2 = (
    b"var Z2=(typeof window!==`undefined`&&typeof window.SAFEROUTE_API_BASE_URL==`string`"
    b"&&window.SAFEROUTE_API_BASE_URL.length>0)?window.SAFEROUTE_API_BASE_URL:"
    b"(typeof location!==`undefined`&&location.origin?location.origin:`http://localhost:8000`)"
)

OLD_FALLBACK = b"t.baseUrl??`http://localhost:8000`"
NEW_FALLBACK = b"t.baseUrl??Z2"

# ---------------------------------------------------------------- Patch 2 --
# Combobox state hook: add one live-suggestions state slot.
OLD_STATE = b"[u,d]=(0,_.useState)(-1),"
NEW_STATE = (
    b"[u,d]=(0,_.useState)(-1),[__srLive,__srSetLive]=(0,_.useState(null)),"
)

# Merged suggestion memo (stays inside the existing `let` declaration).
OLD_MEMO = (
    b"f=(0,_.useMemo)(()=>{let e=a2(o);if(!e)return oW.slice(0,5);let t=[],n=[];"
    b"return oW.forEach(r=>{if(s2(r).includes(e))t.push(r);else{let t=c2(r,e);"
    b"t!==null&&n.push({place:r,score:t})}}),n.sort((e,t)=>e.score-t.score),"
    b"[...t,...n.map(e=>e.place)].slice(0,6)},[o]),"
)
NEW_MEMO = (
    # Merged suggestion list: live Nominatim candidates first (deduplicated by
    # name), then the static presets (offline fallback), capped at 6.
    b"f=(0,_.useMemo)(()=>{"
    b"let e=a2(o),"
    b"__srS=()=>{if(!e)return oW.slice(0,5);let t=[],n=[];"
    b"return oW.forEach(r=>{if(s2(r).includes(e))t.push(r);else{let t=c2(r,e);"
    b"t!==null&&n.push({place:r,score:t})}}),n.sort((e,t)=>e.score-t.score),"
    b"[...t,...n.map(e=>e.place)].slice(0,6)};"
    b"if(!__srLive)return __srS();"
    b"if(!e)return __srLive.slice(0,5);"
    b"let __srSeen=new Set,__srOut=[];"
    b"for(let r of __srLive){let k=(r.name||``).toLowerCase();"
    b"__srSeen.has(k)||(__srSeen.add(k),__srOut.push(r))}"
    b"for(let r of __srS()){let k=(r.name||``).toLowerCase();"
    b"__srSeen.has(k)||(__srSeen.add(k),__srOut.push(r))}"
    b"return __srOut.slice(0,6)},[o,__srLive]),"
)

# Debounced live geocode effect. It MUST be a separate statement after the
# component's `let` declaration, not inserted inside it (that is a syntax error).
OLD_RETURN = b",y=n===`origin`?`${r2.wrap} ${r2.origin}`:r2.wrap;return"
NEW_RETURN = (
    b",y=n===`origin`?`${r2.wrap} ${r2.origin}`:r2.wrap;"
    b"(0,_.useEffect)(()=>{let __srQ=(o||``).trim();if(__srQ.length<2){__srSetLive(null);return}"
    b"let __srC=!1;__srSetLive(null);"
    b"let __srT=window.setTimeout(()=>{"
    b"let __srB=(typeof window.SAFEROUTE_API_BASE_URL==`string`&&window.SAFEROUTE_API_BASE_URL.length>0)"
    b"?window.SAFEROUTE_API_BASE_URL:(location.origin||``);"
    b"fetch(__srB+`/api/geocode`,{method:`POST`,headers:{\"Content-Type\":`application/json`},"
    b"body:JSON.stringify({query:__srQ,limit:6})})"
    b".then(e=>{if(!e.ok)throw new Error(`HTTP `+e.status);return e.json()})"
    b".then(j=>{if(__srC||!j)return;if(j.status!==`ok`||!Array.isArray(j.candidates))return;"
    b"let __srP=j.candidates.map((c,i)=>{"
    b"let dn=String(c.display_name||__srQ),parts=dn.split(`,`),"
    b"nm=(parts[0]||``).trim()||__srQ,rg=parts.slice(1).join(`,`).trim(),"
    b"la=Number(c.latitude),lo=Number(c.longitude);"
    b"return{id:`geocode-`+i+`-`+la+`-`+lo,name:nm,region:rg,lngLat:[lo,la],zoom:14,"
    b"tags:[`geocode`,`live`]}})"
    b".filter(p=>p.name&&Number.isFinite(p.lngLat[0])&&Number.isFinite(p.lngLat[1]));"
    b"__srSetLive(__srP.length?__srP:null)})"
    b".catch(()=>{});},350);"
    b"return()=>{__srC=!0,window.clearTimeout(__srT)}},[o]);return"
)

# Label live suggestions in the dropdown so their source is visible (Rule 20).
OLD_META = b"(0,P.jsx)(`span`,{className:r2.meta,children:e.region})"
NEW_META = (
    b"(0,P.jsx)(`span`,{className:r2.meta,children:e.tags&&e.tags.includes(`live`)"
    b"?`${e.region?e.region+` `:``}(live geocoding - OpenStreetMap)`:e.region})"
)

PATCHES = [
    (OLD_Z2, NEW_Z2, 1, "API base override (Z2)"),
    (OLD_FALLBACK, NEW_FALLBACK, 3, "fetch baseUrl fallbacks"),
    (OLD_STATE, NEW_STATE, 1, "combobox live-suggest state"),
    (OLD_MEMO, NEW_MEMO, 1, "merged live/static suggestion memo"),
    (OLD_RETURN, NEW_RETURN, 1, "live geocode effect after let declaration"),
    (OLD_META, NEW_META, 1, "dropdown live-source label"),
]


def main() -> int:
    data = BUNDLE.read_bytes()
    original = data

    if BACKUP.read_bytes() != original:
        raise SystemExit("ABORT: backup does not match the bundle; restore before patching.")

    for old, new, expected, label in PATCHES:
        count = data.count(old)
        if count != expected:
            raise SystemExit(f"ABORT: anchor for '{label}' found {count}x (expected {expected}).")
        data = data.replace(old, new, expected)

    # No hardcoded base may remain anywhere in the bundle.
    if b"http://localhost:8000" not in original and False:  # pragma: no cover
        pass
    remaining = data.count(b"http://localhost:8000")
    if remaining != 1:  # the final location.origin fallback inside Z2
        raise SystemExit(f"ABORT: unexpected remaining hardcoded base ({remaining}).")

    BUNDLE.write_bytes(data)
    print(f"patched {BUNDLE.name}: {len(original)} -> {len(data)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
