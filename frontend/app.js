// SafeRoute AI — frontend logic (PHASE_18).
// The UI contains NO scoring logic: it only displays verified backend results.
const API_BASE = (window.SAFEROUTE_API || "http://127.0.0.1:8000");

const $ = (id) => document.getElementById(id);
const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
const setStatus = (m) => { $("status").textContent = m; };

function coordInputs() {
  const n = (id) => parseFloat($(id).value);
  return {
    origin: { latitude: n("olat"), longitude: n("olon") },
    destination: { latitude: n("dlat"), longitude: n("dlon") },
  };
}

async function post(path, body) {
  const res = await fetch(API_BASE + path, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error((data.error && data.error.message) || "Request failed");
  return data;
}

function badge(status) {
  const s = status || "unassessed";
  return el("span", "badge " + s, s.replace("_", " "));
}

function renderRoutes(data) {
  const box = $("routes"); box.innerHTML = "";
  const routes = (data && data.routes) || [];
  if (!routes.length) { box.appendChild(el("em", null, "No routes were returned.")); return; }
  const t = el("table"); const hr = el("tr");
  ["Route", "Summary", "Distance", "Segments"].forEach(h => hr.appendChild(el("th", null, h)));
  t.appendChild(hr);
  routes.forEach(r => {
    const tr = el("tr");
    tr.appendChild(el("td", null, r.route_id));
    tr.appendChild(el("td", null, r.summary || ""));
    tr.appendChild(el("td", null, Math.round(r.distance_m) + " m"));
    tr.appendChild(el("td", null, String(r.segments_count)));
    t.appendChild(tr);
  });
  box.appendChild(t);
  if (data.limitations && data.limitations.length) {
    const ul = el("ul", null);
    data.limitations.forEach(l => ul.appendChild(el("li", null, l)));
    box.appendChild(ul);
  }
}

function renderAnalysis(rec) {
  // Routes with scores + coverage
  const box = $("routes"); box.innerHTML = "";
  const t = el("table"); const hr = el("tr");
  ["Route", "Score /100", "Coverage", "Status"].forEach(h => hr.appendChild(el("th", null, h)));
  t.appendChild(hr);
  rec.routes.forEach(r => {
    const tr = el("tr");
    tr.appendChild(el("td", null, r.route_id));
    const sc = el("td"); sc.appendChild(el("span", "score", r.route_score == null ? "—" : r.route_score)); tr.appendChild(sc);
    const cov = (r.coverage && r.coverage.fraction != null) ? Math.round(r.coverage.fraction * 100) + "%" : "—";
    tr.appendChild(el("td", null, cov));
    const st = el("td"); st.appendChild(badge(r.status)); tr.appendChild(st);
    if (r.route_score == null) tr.className = "unassessed-row";
    t.appendChild(tr);
  });
  box.appendChild(t);

  // Comparison
  const c = $("comparison"); c.innerHTML = "";
  const comp = rec.comparison || {};
  if (comp.recommended_route_id) {
    c.appendChild(el("p", null, "Recommended (highest deterministic safety score): " + comp.recommended_route_id));
  } else {
    c.appendChild(el("p", null, "No route can be recommended: no assessable route had sufficient coverage."));
  }
  (comp.unassessed_route_ids || []).forEach(id =>
    c.appendChild(el("p", "unassessed-row", id + " — unassessed (missing/insufficient imagery); never ranked as safe.")));

  // Hazards
  const h = $("hazards"); h.innerHTML = "";
  let total = 0;
  rec.routes.forEach(r => { (r.hazards || []).forEach(x => {
    total++;
    h.appendChild(el("div", "src", `${r.route_id}: ${x.hazard_class} (conf ${(x.confidence||0).toFixed(2)}, severity ${(x.severity||0).toFixed(2)})`));
  }); });
  if (!total) h.appendChild(el("em", null, "No hazards detected on assessed segments (this is not proof of a safe road)."));

  // Explanation
  const ex = $("explanation"); ex.innerHTML = "";
  const e = rec.explanation || {};
  ex.appendChild(el("p", null, e.explanation || ""));
  ex.appendChild(el("p", "src", "source: " + (e.source || "fallback") + " — generated from verified data only"));

  // Disclosures
  const d = $("disclosures"); d.innerHTML = "";
  const ul = el("ul");
  (rec.limitations || []).forEach(l => ul.appendChild(el("li", null, l)));
  (e.disclosures || []).forEach(l => ul.appendChild(el("li", null, l)));
  if (!ul.children.length) ul.appendChild(el("li", null, "No additional limitations reported."));
  d.appendChild(ul);
}

function renderFacilities(data) {
  const f = $("facilities"); f.innerHTML = "";
  f.appendChild(el("p", "src", "Provider: " + (data.provider || "—") + " · status: " + (data.status || "—")));
  const list = data.facilities || [];
  if (!list.length) { f.appendChild(el("em", null, "No facilities reported (not fabricated).")); return; }
  const t = el("table"); const hr = el("tr");
  ["Category", "Name", "Distance", "Source"].forEach(h => hr.appendChild(el("th", null, h)));
  t.appendChild(hr);
  list.forEach(x => {
    const tr = el("tr");
    tr.appendChild(el("td", null, x.category));
    tr.appendChild(el("td", null, x.name));
    tr.appendChild(el("td", null, Math.round(x.distance_m) + " m"));
    tr.appendChild(el("td", null, x.source));
    t.appendChild(tr);
  });
  f.appendChild(t);
}

async function loadFacilities() {
  try {
    const dest = coordInputs().destination;
    const data = await post("/api/facilities", { location: dest, radius_m: 1500 });
    renderFacilities(data);
  } catch (e) {
    $("facilities").innerHTML = "";
    $("facilities").appendChild(el("em", null, "Facilities unavailable: " + e.message));
  }
}

$("btnRoutes").addEventListener("click", async () => {
  setStatus("Finding routes…");
  try { renderRoutes(await post("/api/routes", coordInputs())); setStatus("Routes loaded."); }
  catch (e) { setStatus("Error: " + e.message); }
});

$("btnAnalyze").addEventListener("click", async () => {
  setStatus("Analyzing (this may take a few seconds)…");
  try {
    const rec = await post("/api/analyze", coordInputs());
    renderAnalysis(rec);
    setStatus("Analysis complete: " + rec.status);
    loadFacilities();
  } catch (e) { setStatus("Error: " + e.message); }
});
