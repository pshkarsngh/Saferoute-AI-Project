// SafeRoute AI — frontend logic.
// The UI contains NO scoring logic: it only displays verified backend results
// and forwards place names to the backend geocoder. Rule 7, Rule 12.
const API_BASE = (window.SAFEROUTE_API || "");
const $ = (id) => document.getElementById(id);
const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
const setStatus = (m) => { $("status").textContent = m; };

const state = { origin: null, destination: null, map: null, markers: [], lines: [] };

// ---------------------------------------------------------------- map ----
function initMap() {
  if (!window.L) { $("map").innerHTML = "<em>Map library unavailable (offline). Use manual coordinates.</em>"; return; }
  state.map = L.map("map").setView([12.9716, 77.5946], 11);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, attribution: "&copy; OpenStreetMap contributors",
  }).addTo(state.map);
  state.map.on("click", (e) => {
    state.destination = { latitude: e.latlng.lat, longitude: e.latlng.lng };
    $("dlat").value = e.latlng.lat.toFixed(5);
    $("dlon").value = e.latlng.lng.toFixed(5);
    drawPoint("destination");
    setStatus("Destination set from map click.");
  });
}

function clearLayer(kind) {
  state[kind].forEach((l) => state.map && state.map.removeLayer(l));
  state[kind] = [];
}

function drawPoint(kind) {
  if (!state.map) return;
  state.markers = state.markers.filter((m) => { if (m._srKind === kind) { state.map.removeLayer(m); return false; } return true; });
  const c = state[kind];
  if (!c) return;
  const color = kind === "origin" ? "#22c55e" : "#ef4444";
  const m = L.circleMarker([c.latitude, c.longitude], { radius: 8, color, fillOpacity: 0.9 }).addTo(state.map);
  m._srKind = kind;
  state.markers.push(m);
  state.map.fitBounds([[c.latitude, c.longitude], [c.latitude, c.longitude]], { maxZoom: 13 });
}

function drawRoutes(routes) {
  if (!state.map) return;
  clearLayer("lines");
  const bounds = [];
  routes.forEach((r) => {
    const geom = r.geometry && r.geometry.coordinates;
    if (!geom || !geom.length) return;
    const latlngs = geom.map((c) => [c[1], c[0]]);
    bounds.push(...latlngs);
    const recommended = r.route_id === (state.recommended || "");
    const color = r.route_score == null ? "#64748b" : (recommended ? "#22c55e" : "#38bdf8");
    const line = L.polyline(latlngs, { color, weight: recommended ? 6 : 4, opacity: 0.85 }).addTo(state.map);
    line.bindPopup(`${r.route_id}${r.route_score != null ? " — score " + r.route_score : " — unassessed"}`);
    state.lines.push(line);
  });
  if (bounds.length) state.map.fitBounds(bounds, { padding: [20, 20] });
}

// ------------------------------------------------------------ geocoding ---
async function geocode(query) {
  const res = await fetch(API_BASE + "/api/geocode", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error((data.error && data.error.message) || data.error_message || "Geocoding failed");
  return data.candidates || [];
}

async function searchDestination() {
  const q = $("destQuery").value.trim();
  if (!q) { setStatus("Type a destination first."); return; }
  setStatus("Searching…");
  try {
    const cands = await geocode(q);
    const list = $("geoCandidates"); list.innerHTML = "";
    cands.slice(0, 5).forEach((c) => { const o = el("option"); o.value = c.display_name; list.appendChild(o); });
    if (!cands.length) { setStatus("No place found for that name."); return; }
    const best = cands[0];
    state.destination = { latitude: best.latitude, longitude: best.longitude };
    $("destQuery").value = best.display_name;
    $("dlat").value = best.latitude; $("dlon").value = best.longitude;
    drawPoint("destination");
    setStatus("Destination: " + best.display_name);
  } catch (e) { setStatus("Error: " + e.message); }
}

function useMyLocation() {
  if (!navigator.geolocation) { setStatus("Geolocation not supported by this browser."); return; }
  setStatus("Locating…");
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      state.origin = { latitude: pos.coords.latitude, longitude: pos.coords.longitude };
      drawPoint("origin");
      setStatus("Origin set from device location.");
    },
    (err) => setStatus("Location error: " + err.message),
    { enableHighAccuracy: true, timeout: 10000 }
  );
}

// -------------------------------------------------------------- payload ---
function manualCoord(latId, lonId) {
  const a = parseFloat($(latId).value), b = parseFloat($(lonId).value);
  return (Number.isFinite(a) && Number.isFinite(b)) ? { latitude: a, longitude: b } : null;
}
function locationPayload() {
  const p = {};
  const o = manualCoord("olat", "olon");
  if (o) p.origin = o; else if (state.origin) p.origin = state.origin;
  else if ($("originQuery").value.trim()) p.origin_query = $("originQuery").value.trim();

  const d = manualCoord("dlat", "dlon");
  if (d) p.destination = d; else if (state.destination) p.destination = state.destination;
  else if ($("destQuery").value.trim()) p.destination_query = $("destQuery").value.trim();
  return p;
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
  return el("span", "badge " + s, s.replace(/_/g, " "));
}

// ------------------------------------------------------------- render -----
function renderRoutes(data) {
  const box = $("routes"); box.innerHTML = "";
  const routes = (data && data.routes) || [];
  if (!routes.length) { box.appendChild(el("em", null, "No routes were returned.")); return; }
  const t = el("table"); const hr = el("tr");
  ["Route", "Summary", "Distance", "Segments"].forEach((h) => hr.appendChild(el("th", null, h)));
  t.appendChild(hr);
  routes.forEach((r) => {
    const tr = el("tr");
    tr.appendChild(el("td", null, r.route_id));
    tr.appendChild(el("td", null, r.summary || ""));
    tr.appendChild(el("td", null, Math.round(r.distance_m) + " m"));
    tr.appendChild(el("td", null, String(r.segments_count != null ? r.segments_count : (r.segments || []).length)));
    t.appendChild(tr);
  });
  box.appendChild(t);
  if (data.limitations && data.limitations.length) {
    const ul = el("ul", null);
    data.limitations.forEach((l) => ul.appendChild(el("li", null, l)));
    box.appendChild(ul);
  }
}

function renderAnalysis(rec) {
  state.recommended = (rec.comparison || {}).recommended_route_id || "";

  const box = $("routes"); box.innerHTML = "";
  const t = el("table"); const hr = el("tr");
  ["Route", "Score /100", "Coverage", "Status", "Finding"].forEach((h) => hr.appendChild(el("th", null, h)));
  t.appendChild(hr);
  (rec.routes || []).forEach((r) => {
    const tr = el("tr");
    tr.appendChild(el("td", null, r.route_id));
    const sc = el("td"); sc.appendChild(el("span", "score", r.route_score == null ? "—" : r.route_score)); tr.appendChild(sc);
    const cov = (r.coverage && r.coverage.fraction != null) ? Math.round(r.coverage.fraction * 100) + "%" : "—";
    tr.appendChild(el("td", null, cov));
    const st = el("td"); st.appendChild(badge(r.status)); tr.appendChild(st);
    const finding = el("td", "src", (r.detection_outcome || "unassessed").replace(/_/g, " "));
    tr.appendChild(finding);
    if (r.route_score == null) tr.className = "unassessed-row";
    t.appendChild(tr);
  });
  box.appendChild(t);
  drawRoutes(rec.routes || []);

  const c = $("comparison"); c.innerHTML = "";
  const comp = rec.comparison || {};
  const ranked = comp.ranking || [];
  const reco = ranked.find((x) => x.route_id === comp.recommended_route_id);
  if (comp.recommended_route_id) {
    c.appendChild(el("p", null, "Recommended (highest deterministic safety score): " + comp.recommended_route_id));
    if (reco && reco.safety_note) c.appendChild(el("p", "src", reco.safety_note));
  } else {
    c.appendChild(el("p", null, "No route can be recommended: no assessable route had sufficient coverage."));
  }
  (comp.unassessed_route_ids || []).forEach((id) =>
    c.appendChild(el("p", "unassessed-row", id + " — unassessed (missing/insufficient imagery); never ranked as safe.")));
  if (comp.note) c.appendChild(el("p", "src", comp.note));

  const h = $("hazards"); h.innerHTML = "";
  let total = 0;
  (rec.routes || []).forEach((r) => { (r.hazards || []).forEach((x) => {
    total++;
    h.appendChild(el("div", "src", `${r.route_id}: ${x.hazard_class} (conf ${(x.confidence || 0).toFixed(2)}, severity ${(x.severity || 0).toFixed(2)})`));
  }); });
  if (!total) h.appendChild(el("em", null, "No hazards detected on assessed segments (this is not proof of a safe road)."));

  const ex = $("explanation"); ex.innerHTML = "";
  const e = rec.explanation || {};
  ex.appendChild(el("p", null, e.explanation || ""));
  ex.appendChild(el("p", "src", "source: " + (e.source || "fallback") + " — generated from verified data only"));

  const d = $("disclosures"); d.innerHTML = "";
  const ul = el("ul");
  if (rec.provider) ul.appendChild(el("li", "src", "Routing provider: " + rec.provider));
  (rec.limitations || []).forEach((l) => ul.appendChild(el("li", null, l)));
  (e.disclosures || []).forEach((l) => ul.appendChild(el("li", null, l)));
  if (!ul.children.length) ul.appendChild(el("li", null, "No additional limitations reported."));
  d.appendChild(ul);
}

function renderFacilities(data) {
  const f = $("facilities"); f.innerHTML = "";
  f.appendChild(el("p", "src", "Provider: " + (data.provider || "—") + " · status: " + (data.status || "—")));
  const list = data.facilities || [];
  if (!list.length) { f.appendChild(el("em", null, "No facilities reported (not fabricated).")); return; }
  const t = el("table"); const hr = el("tr");
  ["Category", "Name", "Distance", "Source"].forEach((h) => hr.appendChild(el("th", null, h)));
  t.appendChild(hr);
  list.forEach((x) => {
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
    const p = locationPayload();
    const loc = p.destination || (state.destination ? state.destination : null);
    if (!loc) { $("facilities").innerHTML = "<em>Set a destination to load facilities.</em>"; return; }
    const data = await post("/api/facilities", { location: loc, radius_m: 1500 });
    renderFacilities(data);
  } catch (e) {
    $("facilities").innerHTML = "";
    $("facilities").appendChild(el("em", null, "Facilities unavailable: " + e.message));
  }
}

// -------------------------------------------------------------- events ----
$("btnSearch").addEventListener("click", searchDestination);
$("btnMyLocation").addEventListener("click", useMyLocation);
$("destQuery").addEventListener("keydown", (e) => { if (e.key === "Enter") searchDestination(); });

$("btnRoutes").addEventListener("click", async () => {
  setStatus("Finding routes…");
  try { const data = await post("/api/routes", locationPayload()); renderRoutes(data); drawRoutes(data.routes || []); setStatus("Routes loaded."); }
  catch (e) { setStatus("Error: " + e.message); }
});

$("btnAnalyze").addEventListener("click", async () => {
  setStatus("Analyzing (this may take a few seconds)…");
  try {
    const rec = await post("/api/analyze", locationPayload());
    renderAnalysis(rec);
    setStatus("Analysis complete: " + rec.status);
    loadFacilities();
  } catch (e) { setStatus("Error: " + e.message); }
});

async function loadProviderInfo() {
  try {
    const res = await fetch(API_BASE + "/api/health");
    const d = await res.json();
    const p = d.providers || {};
    $("providerLine").textContent = `routing: ${p.routing} · imagery: ${p.imagery} · facilities: ${p.facilities} · geocoding: ${p.geocoding || "off"} · explanation: ${p.llm}`;
  } catch (_) { /* ignore */ }
}

initMap();
loadProviderInfo();
