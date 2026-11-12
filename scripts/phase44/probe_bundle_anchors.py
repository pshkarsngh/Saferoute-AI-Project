"""Probe anchor occurrence counts in the shipped frontend bundle (PHASE_44)."""

from pathlib import Path

BUNDLE = Path(__file__).resolve().parents[2] / "frontend" / "assets" / "index-CXsvefbt.js"

ANCHORS = {
    "Z2 declaration": b"var Z2=`http://localhost:8000`",
    "baseUrl fallback": b"t.baseUrl??`http://localhost:8000`",
    "combobox index state": b"[u,d]=(0,_.useState)(-1),",
    "static memo": (
        b"f=(0,_.useMemo)(()=>{let e=a2(o);if(!e)return oW.slice(0,5);let t=[],n=[];"
        b"return oW.forEach(r=>{if(s2(r).includes(e))t.push(r);else{let t=c2(r,e);"
        b"t!==null&&n.push({place:r,score:t})}}),n.sort((e,t)=>e.score-t.score),"
        b"[...t,...n.map(e=>e.place)].slice(0,6)},[o]),"
    ),
    "meta span": b"(0,P.jsx)(`span`,{className:r2.meta,children:e.region})",
    "localhost literal": b"http://localhost:8000",
}


def main() -> int:
    data = BUNDLE.read_bytes()
    for name, anchor in ANCHORS.items():
        print(f"{name}: {data.count(anchor)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
