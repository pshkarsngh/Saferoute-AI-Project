// SafeRoute AI — frontend logic.
// The UI contains NO scoring logic: it only displays verified backend results
// and forwards place names to the backend geocoder. Rule 7, Rule 12.
const API_BASE = (window.SAFEROUTE_API || "");
const $ = (id) => document.getElementById(id);
const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
const setStatus = (m) => { $("status").textContent = m; };

const state = { origin: null, destination: null, map: null, markers: [], lines: [], hazardMarkers: [] };

// --------------------------------------------------------- formatting ----
// Presentation-only helpers. The UI performs NO scoring (Rule 7): every number
// shown below comes verbatim from the verified backend record.
const fmtDist = (m) => (m == null ? "—" : (m >= 1000 ? (m / 1000).toFixed(2) + " km" : Math.round(m) + " m"));
const fmtDur = (s) => (s == null ? "—" : (s >= 60 ? Math.floor(s / 60) + " min " + Math.round(s % 60) + " s" : Math.round(s) + " s"));
const pct = (f) => (f == null ? "—" : Math.round(f * 100) + "%");
const classes = (route) => {
  const seen = [];
  (route.hazards || []).forEach((h) => { if (h.hazard_class && seen.indexOf(h.hazard_class) < 0) seen.push(h.hazard_class); });
  return seen.join(", ");
};

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
  (state.hazardMarkers || []).forEach((m) => state.map.removeLayer(m));
  state.hazardMarkers = [];
  const bounds = [];
  routes.forEach((r) => {
    const geom = r.geometry && r.geometry.coordinates;
    if (!geom || !geom.length) return;
    const latlngs = geom.map((c) => [c[1], c[0]]);
    bounds.push(...latlngs);
    const recommended = r.route_id === (state.recommended || "");
    const color = r.route_score == null ? "#64748b" : (recommended ? "#22c55e" : "#38bdf8");
    const line = L.polyline(latlngs, { color, weight: recommended ? 6 : 4, opacity: 0.85 }).addTo(state.map);
    const cov = (r.assessed_length_fraction != null) ? r.assessed_length_fraction
              : (r.coverage && r.coverage.fraction);
    line.bindPopup(
      `${r.route_id}${recommended ? " ★ recommended" : ""}<br>` +
      `score: ${r.route_score != null ? r.route_score : "unassessed"} / 100<br>` +
      `distance: ${fmtDist(r.distance_m)} · time: ${fmtDur(r.duration_s)}<br>` +
      `assessed length: ${pct(cov)} · hazards: ${r.hazards_total != null ? r.hazards_total : "—"}`);
    state.lines.push(line);

    // Segment-level hazard locations (approximate: midpoint of the verified
    // segment geometry; NOT precise hazard coordinates). Derived only from
    // backend-provided segment coordinates and detections.
    const bySeg = {};
    (r.hazards || []).forEach((h) => { if (h.segment_id) (bySeg[h.segment_id] = bySeg[h.segment_id] || []).push(h); });
    Object.keys(bySeg).forEach((segId) => {
      const seg = (r.segments || []).find((s) => s.segment_id === segId);
      if (!seg || !seg.start_coord || !seg.end_coord) return;
      const lat = (seg.start_coord.latitude + seg.end_coord.latitude) / 2;
      const lon = (seg.start_coord.longitude + seg.end_coord.longitude) / 2;
      const cs = bySeg[segId].map((h) => h.hazard_class).join(", ");
      const mk = L.circleMarker([lat, lon], { radius: 7, color: "#f59e0b", fillOpacity: 0.85 }).addTo(state.map);
      mk.bindPopup(`${r.route_id} · segment ${segId}<br>hazards: ${cs}<br>` +
                   `<span>Segment-level location (approximate midpoint; not precise hazard coordinates).</span>`);
      state.hazardMarkers.push(mk);
    });
  });
  if (bounds.length) state.map.fitBounds(bounds, { padding: [20, 20] });
  const legend = document.getElementById("mapLegend");
  if (legend) legend.innerHTML =
    '<strong>Legend:</strong> green = recommended route · blue = assessed alternative · ' +
    'grey = unassessed (never ranked as safe) · amber dots = segments with detected hazards (approximate).';
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

function renderRecommendation(rec) {
  const box = $("recommendation"); box.innerHTML = "";
  const comp = rec.comparison || {};
  const routes = rec.routes || [];

  if (routes.some((r) => r.evidence_class === "demo")) {
    box.appendChild(el("p", "warn",
      "⚠ Demo imagery (not geographically matched to the requested roads) contributed to " +
      "some scores. Those routes are pipeline demonstrations only and are excluded from the " +
      "recommendation (Rule 9, Rule 20)."));
  }

  if (comp.recommendation_status === "recommended" && comp.recommended_route_id) {
    const entry = (comp.ranking || []).find((x) => x.route_id === comp.recommended_route_id) || {};
    box.appendChild(el("h3", "reco-title recommended",
      "Recommended: " + comp.recommended_route_id + " — score " +
      (entry.route_score != null ? entry.route_score : "—") + " / 100"));
    box.appendChild(el("p", "hint",
      "Highest deterministic safety score among sufficiently assessed routes. The detector " +
      "covers pothole and crack only, and a high score is not proof that the road is safe."));
    const ul = el("ul", "reasons");
    (comp.recommendation_reasons || []).forEach((x) => ul.appendChild(el("li", null, x)));
    if (ul.children.length) box.appendChild(ul);
  } else {
    box.appendChild(el("h3", "reco-title cannot", "Safest route cannot currently be determined"));
    box.appendChild(el("p", null,
      comp.cannot_determine_reason ||
      "No route had sufficient assessed evidence for a defensible comparison."));
    if ((comp.tied_route_ids || []).length) {
      box.appendChild(el("p", "src", "Tied on deterministic score: " + comp.tied_route_ids.join(", ")));
    }
    box.appendChild(el("p", "hint",
      "No route is presented as safe. Missing or insufficient evidence is never treated as " +
      "proof of safety."));
  }

  if ((comp.unassessed_route_ids || []).length) {
    box.appendChild(el("p", "unassessed-row",
      "Unassessed (not ranked): " + comp.unassessed_route_ids.join(", ")));
  }
}

function renderAnalysis(rec) {
  const comp = rec.comparison || {};
  state.recommended = comp.recommended_route_id || "";
  const rankById = {};
  (comp.ranking || []).forEach((e) => { rankById[e.route_id] = e; });

  renderRecommendation(rec);

  const box = $("routes"); box.innerHTML = "";
  const t = el("table"); const hr = el("tr");
  ["#", "Route", "Score /100", "Distance", "Time", "Assessed", "Hazards", "Status", "Why (verified)"]
    .forEach((h) => hr.appendChild(el("th", null, h)));
  t.appendChild(hr);

  const ordered = (rec.routes || []).slice().sort((a, b) => {
    const ra = rankById[a.route_id], rb = rankById[b.route_id];
    if (ra && rb) return ra.rank - rb.rank;
    if (ra) return -1;
    if (rb) return 1;
    return 0;
  });

  ordered.forEach((r) => {
    const e = rankById[r.route_id] || {};
    const tr = el("tr");
    const isReco = r.route_id === comp.recommended_route_id;
    if (isReco) tr.className = "recommended-row";
    tr.appendChild(el("td", null, e.rank != null ? String(e.rank) : "—"));
    tr.appendChild(el("td", null, r.route_id + (isReco ? " ★" : "")));
    const sc = el("td"); sc.appendChild(el("span", "score", r.route_score == null ? "—" : String(r.route_score))); tr.appendChild(sc);
    tr.appendChild(el("td", null, fmtDist(r.distance_m)));
    tr.appendChild(el("td", null, fmtDur(r.duration_s)));
    const frac = (e.assessed_length_fraction != null) ? e.assessed_length_fraction
               : (r.coverage ? r.coverage.fraction : null);
    tr.appendChild(el("td", null, pct(frac)));
    tr.appendChild(el("td", null, r.route_score == null ? "—" : String(r.hazards_total != null ? r.hazards_total : 0)));
    const st = el("td"); st.appendChild(badge(r.status));
    if (r.evidence_class === "demo") st.appendChild(el("span", "badge demo", "demo"));
    tr.appendChild(st);
    const why = el("td", "why");
    if (r.route_score == null) {
      why.textContent = "Not assessed: missing or insufficient imagery — never presented as safe.";
    } else if ((e.reasons || []).length) {
      why.textContent = e.reasons.slice(0, 3).join(" ");
    } else {
      why.textContent = e.safety_note || "";
    }
    tr.appendChild(why);
    if (r.route_score == null) tr.className = (tr.className + " unassessed-row").trim();
    t.appendChild(tr);
  });
  box.appendChild(t);
  if (rec.limitations && rec.limitations.length) {
    const ul = el("ul", null);
    rec.limitations.forEach((l) => ul.appendChild(el("li", null, l)));
    box.appendChild(ul);
  }
  drawRoutes(rec.routes || []);

  const c = $("comparison"); c.innerHTML = "";
  if (comp.recommendation_status === "recommended") {
    const others = (comp.ranking || []).filter((x) => x.route_id !== comp.recommended_route_id);
    if (others.length) {
      c.appendChild(el("p", null, "Relative to the recommended route " + comp.recommended_route_id + ":"));
      const ul = el("ul");
      others.forEach((x) => {
        const bits = [];
        if (x.score_delta_vs_recommended != null) bits.push((x.score_delta_vs_recommended >= 0 ? "+" : "") + x.score_delta_vs_recommended + " score");
        if (x.distance_delta_vs_recommended) bits.push((x.distance_delta_vs_recommended > 0 ? "+" : "") + Math.round(x.distance_delta_vs_recommended) + " m");
        if (x.duration_delta_vs_recommended) bits.push((x.duration_delta_vs_recommended > 0 ? "+" : "") + Math.round(x.duration_delta_vs_recommended) + " s");
        ul.appendChild(el("li", null, x.route_id + ": " + (bits.join(", ") || "no difference in score, distance or time")));
      });
      c.appendChild(ul);
    }
  }
  (comp.unassessed_route_ids || []).forEach((id) =>
    c.appendChild(el("p", "unassessed-row", id + " — unassessed (missing/insufficient imagery); never ranked as safe.")));
  if (comp.note) c.appendChild(el("p", "src", comp.note));

  const h = $("hazards"); h.innerHTML = "";
  let total = 0;
  (rec.routes || []).forEach((r) => { (r.hazards || []).forEach((x) => {
    total++;
    h.appendChild(el("div", "src",
      `${r.route_id} · segment ${x.segment_id || "—"}: ${x.hazard_class} ` +
      `(conf ${(x.confidence || 0).toFixed(2)}, severity ${(x.severity || 0).toFixed(2)})`));
  }); });
  if (!total) h.appendChild(el("em", null, "No hazards detected on assessed segments (this is not proof of a safe road)."));

  const ex = $("explanation"); ex.innerHTML = "";
  const e = rec.explanation || {};
  ex.appendChild(el("p", null, e.explanation || ""));
  ex.appendChild(el("p", "src", "source: " + (e.source || "fallback") + " — generated from verified data only"));

  const d = $("disclosures"); d.innerHTML = "";
  const ul = el("ul");
  if (rec.provider) ul.appendChild(el("li", "src", "Routing provider: " + rec.provider));
  if (rec.created_at) ul.appendChild(el("li", "src", "Assessment timestamp: " + rec.created_at));
  if (rec.model_version) ul.appendChild(el("li", "src", "Detector: " + rec.model_version +
    (rec.config_hash ? " · scoring config " + String(rec.config_hash).slice(0, 12) + "…" : "")));
  if ((rec.routes || []).some((r) => r.evidence_class === "demo")) {
    ul.appendChild(el("li", "warn", "Demo imagery was used for at least one route — excluded from the recommendation and never evidence about the requested roads."));
  }
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
