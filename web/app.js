(() => {
  "use strict";

  const PRIORITY_COLORS = {
    ram_inthra: "#4cc9f0",
    prasert_manukitch: "#65d49a",
    pradit_manutham: "#f0b55a",
    nuan_chan: "#b89cff"
  };

  const CLASS_LABELS = {
    VERY_HIGH_FOR_TIME: "สูงมากเมื่อเทียบกับช่วงเวลาปกติ",
    HIGH_FOR_TIME: "สูงกว่าปกติของช่วงเวลานี้",
    TYPICAL_FOR_TIME: "อยู่ในช่วงปกติของเวลานี้",
    LOW_FOR_TIME: "ต่ำกว่าปกติของช่วงเวลานี้",
    VERY_LOW_FOR_TIME: "ต่ำมากเมื่อเทียบกับช่วงเวลาปกติ",
    UNKNOWN: "ยังประเมิน baseline ไม่ได้"
  };

  let statusData = null;
  let networkData = null;
  let selectedRoad = "all";
  let mapProjection = null;

  const $ = (id) => document.getElementById(id);

  function safeStorageGet(key) {
    try { return window.localStorage ? window.localStorage.getItem(key) : null; }
    catch (_) { return null; }
  }

  function safeStorageSet(key, value) {
    try { if (window.localStorage) window.localStorage.setItem(key, value); }
    catch (_) {}
  }

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function roadMeta(id) {
    return statusData?.roads?.[id] || { display_name: id, priority: false, confirmed_incident_count: 0 };
  }

  function roadLabel(id) {
    return roadMeta(id).display_name || id;
  }

  function roadColor(id) {
    if (PRIORITY_COLORS[id]) return PRIORITY_COLORS[id];
    if ((roadMeta(id).confirmed_incident_count || 0) > 0) return cssVar("--accent-2");
    return cssVar("--subtle");
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatThaiDate(value) {
    if (!value) return "—";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    return new Intl.DateTimeFormat("th-TH", {
      timeZone: "Asia/Bangkok",
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit"
    }).format(d);
  }

  function formatRunId(runId) {
    if (!runId || !/^\d{8}T\d{6}Z$/.test(runId)) return runId || "—";
    const iso = runId.slice(0, 4) + "-" + runId.slice(4, 6) + "-" + runId.slice(6, 8)
      + "T" + runId.slice(9, 11) + ":" + runId.slice(11, 13) + ":" + runId.slice(13, 15) + "Z";
    return formatThaiDate(iso);
  }

  function allIncidents() {
    if (!statusData) return [];
    const incidents = [];
    Object.entries(statusData.roads || {}).forEach(([roadId, road]) => {
      (road.confirmed_incidents || []).forEach((item) => incidents.push({ ...item, road_id: roadId }));
    });
    return incidents.sort((a, b) => String(b.latest_start || "").localeCompare(String(a.latest_start || "")));
  }

  function priorityRoadIds() {
    return Object.entries(statusData?.roads || {})
      .filter(([, road]) => road.priority)
      .map(([id]) => id);
  }

  function incidentRoadIds() {
    return Object.entries(statusData?.roads || {})
      .filter(([, road]) => (road.confirmed_incident_count || 0) > 0)
      .sort((a, b) => (b[1].confirmed_incident_count || 0) - (a[1].confirmed_incident_count || 0))
      .map(([id]) => id);
  }

  function renderMetrics() {
    const ti = statusData.city_context.traffic_index;
    const base = statusData.city_context.traffic_index_baseline.baseline;
    $("trafficIndexValue").textContent = Number(ti.index).toFixed(1);
    $("trafficIndexStatus").textContent = CLASS_LABELS[base.classification] || base.classification;
    $("trafficIndexBaseline").textContent =
      "ค่ากลาง " + Number(base.median).toFixed(1)
      + " · P" + Number(base.current_percentile_rank).toFixed(0)
      + " · n=" + base.sample_count;

    $("incidentCount").textContent = statusData.network_incidents.distinct_confirmed_incidents;
    const activeRoads = statusData.network_summary?.roads_with_confirmed_incidents || 0;
    const roadCount = statusData.network_summary?.road_count || Object.keys(statusData.roads || {}).length;
    $("incidentBreakdown").textContent = "ครอบคลุม " + roadCount + " ถนนหลัก · มีเหตุบน " + activeRoads + " ถนน";

    const speedReady = statusData.source_status.segment_speed !== "UNAVAILABLE";
    $("speedValue").textContent = speedReady ? "ทดลอง" : "N/A";
    $("speedStatus").textContent = speedReady
      ? "มี experimental speed source"
      : "รอ provider/API access สำหรับความเร็วรายช่วงถนน";

    const event = statusData.source_details?.events || {};
    const age = event.latest_event_age_hours;
    $("latestEventAge").textContent = age == null ? "LIVE" : Math.round(age * 60) + " นาที";
    $("latestEventTime").textContent = event.latest_event_start
      ? "เหตุล่าสุด " + formatThaiDate(event.latest_event_start)
      : "ไม่พบ source timestamp";

    const live = statusData.source_status.events === "LIVE";
    $("freshnessText").textContent = live
      ? "Live incident feed · build " + formatRunId(statusData.generated_from_run)
      : "Incident feed: " + statusData.source_status.events;
    document.querySelector(".status-dot").style.background = live ? cssVar("--ready") : cssVar("--warning");
  }

  function renderLegend() {
    const priority = priorityRoadIds().map((id) =>
      '<div class="legend-item"><span class="legend-line" style="background:' + roadColor(id) + '"></span>'
      + escapeHtml(roadLabel(id).replace("ถนน", "")) + "</div>"
    );
    priority.push('<div class="legend-item"><span class="legend-line" style="background:' + cssVar("--subtle") + '"></span>ถนนหลักอื่น</div>');
    $("mapLegend").innerHTML = priority.join("");
  }

  function computeProjection() {
    const coords = [];
    (networkData.features || []).forEach((f) => {
      ((f.geometry || {}).coordinates || []).forEach((p) => coords.push(p));
    });
    if (!coords.length) return null;
    const lons = coords.map((p) => Number(p[0]));
    const lats = coords.map((p) => Number(p[1]));
    const minLon = Math.min(...lons), maxLon = Math.max(...lons);
    const minLat = Math.min(...lats), maxLat = Math.max(...lats);
    const W = 1000, H = 620, P = 36;
    return (lon, lat) => {
      const x = P + ((lon - minLon) / Math.max(maxLon - minLon, 1e-8)) * (W - 2 * P);
      const y = H - P - ((lat - minLat) / Math.max(maxLat - minLat, 1e-8)) * (H - 2 * P);
      return [x, y];
    };
  }

  function svgEl(tag, attrs = {}) {
    const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, String(v)));
    return el;
  }

  function pathFromCoords(coords) {
    return coords.map((p, i) => {
      const [x, y] = mapProjection(Number(p[0]), Number(p[1]));
      return (i ? "L" : "M") + x.toFixed(1) + " " + y.toFixed(1);
    }).join(" ");
  }

  function renderMap() {
    const svg = $("networkMap");
    svg.innerHTML = "";
    mapProjection = computeProjection();
    $("mapEmpty").hidden = Boolean(mapProjection);
    if (!mapProjection) return;

    const roadGroup = svgEl("g", { class: "roads-layer" });
    const pointGroup = svgEl("g", { class: "incidents-layer" });
    const labelGroup = svgEl("g", { class: "labels-layer" });
    const priorityBuckets = {};

    (networkData.features || []).forEach((feature) => {
      const roadId = feature.properties?.road_id;
      const coords = feature.geometry?.coordinates || [];
      if (!roadId || coords.length < 2) return;
      const meta = roadMeta(roadId);
      const path = svgEl("path", {
        d: pathFromCoords(coords),
        class: "network-road" + (meta.priority ? " is-priority" : ""),
        "data-road": roadId,
        stroke: roadColor(roadId)
      });
      path.addEventListener("click", () => selectRoad(roadId));
      roadGroup.appendChild(path);
      if (meta.priority) {
        priorityBuckets[roadId] ||= [];
        priorityBuckets[roadId].push(...coords);
      }
    });

    Object.entries(priorityBuckets).forEach(([roadId, coords]) => {
      if (!coords.length) return;
      const avgLon = coords.reduce((s, p) => s + Number(p[0]), 0) / coords.length;
      const avgLat = coords.reduce((s, p) => s + Number(p[1]), 0) / coords.length;
      const [x, y] = mapProjection(avgLon, avgLat);
      const label = svgEl("text", {
        x: x.toFixed(1),
        y: y.toFixed(1),
        class: "road-label",
        "text-anchor": "middle",
        "data-road-label": roadId
      });
      label.textContent = roadLabel(roadId).replace("ถนน", "");
      labelGroup.appendChild(label);
    });

    allIncidents().forEach((incident) => {
      const lon = Number(incident.longitude);
      const lat = Number(incident.latitude);
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) return;
      const [x, y] = mapProjection(lon, lat);
      const g = svgEl("g", {
        class: "incident-point",
        "data-road": incident.road_id,
        transform: "translate(" + x.toFixed(1) + " " + y.toFixed(1) + ")"
      });
      g.appendChild(svgEl("circle", { r: 11, class: "incident-halo" }));
      g.appendChild(svgEl("circle", { r: 5, class: "incident-core" }));
      g.addEventListener("mouseenter", (ev) => showTooltip(ev, incident));
      g.addEventListener("mouseleave", hideTooltip);
      g.addEventListener("click", () => selectRoad(incident.road_id));
      pointGroup.appendChild(g);
    });

    svg.append(roadGroup, labelGroup, pointGroup);
    updateMapSelection();
  }

  function showTooltip(event, incident) {
    const tip = $("mapTooltip");
    tip.innerHTML = "<strong>" + escapeHtml(incident.title || "เหตุการณ์") + "</strong>"
      + escapeHtml(roadLabel(incident.road_id)) + "<br>"
      + escapeHtml(formatThaiDate(incident.latest_start));
    const rect = $("mapStage").getBoundingClientRect();
    tip.style.left = Math.min(event.clientX - rect.left + 12, rect.width - 300) + "px";
    tip.style.top = Math.max(event.clientY - rect.top - 18, 8) + "px";
    tip.hidden = false;
  }

  function hideTooltip() { $("mapTooltip").hidden = true; }

  function filterRoadIds() {
    const ids = [...priorityRoadIds()];
    incidentRoadIds().forEach((id) => { if (!ids.includes(id)) ids.push(id); });
    return ids;
  }

  function renderFilters() {
    const chips = [
      { id: "all", label: "ทั้งหมด", count: allIncidents().length },
      ...filterRoadIds().map((id) => ({
        id,
        label: roadLabel(id).replace("ถนน", ""),
        count: roadMeta(id).confirmed_incident_count || 0
      }))
    ];
    $("incidentFilters").innerHTML = chips.map((chip) =>
      '<button type="button" class="filter-chip ' + (selectedRoad === chip.id ? "is-active" : "")
      + '" data-filter="' + chip.id + '">' + escapeHtml(chip.label) + " " + chip.count + "</button>"
    ).join("");
    $("incidentFilters").querySelectorAll("button").forEach((btn) => {
      btn.addEventListener("click", () => selectRoad(btn.dataset.filter));
    });
  }

  function renderIncidents() {
    const incidents = allIncidents().filter((x) => selectedRoad === "all" || x.road_id === selectedRoad);
    if (!incidents.length) {
      $("incidentList").innerHTML = '<div class="empty-list">ยังไม่พบเหตุที่ยืนยันได้ในตัวกรองนี้</div>';
      return;
    }
    $("incidentList").innerHTML = incidents.map((item) => {
      const duplicateText = item.record_count > 1 ? " · รวม " + item.record_count + " records" : "";
      const refs = (item.event_route_refs || []).length ? " · ทล." + item.event_route_refs.join(", ") : "";
      return '<article class="incident-item">'
        + '<div class="incident-item-top">'
        + '<span class="incident-marker" style="background:' + roadColor(item.road_id) + '"></span>'
        + '<div class="incident-title">' + escapeHtml(item.title || "เหตุการณ์") + "</div>"
        + "</div>"
        + '<div class="incident-meta">' + escapeHtml(roadLabel(item.road_id))
        + " · " + escapeHtml(formatThaiDate(item.latest_start))
        + escapeHtml(refs + duplicateText) + "</div>"
        + "</article>";
    }).join("");
  }

  function cardRoadIds() {
    const priority = priorityRoadIds();
    const active = incidentRoadIds().filter((id) => !priority.includes(id));
    return [...priority, ...active.slice(0, 8)];
  }

  function renderRoadCards() {
    $("roadCards").innerHTML = cardRoadIds().map((id) => {
      const road = roadMeta(id);
      const incidents = road.confirmed_incident_count || 0;
      const selected = selectedRoad === id ? " is-selected" : "";
      return '<article class="road-card' + selected + '" data-road-card="' + id
        + '" style="--road-color:' + roadColor(id) + '">'
        + '<div class="road-card-line"></div>'
        + "<h3>" + escapeHtml(road.display_name || id) + "</h3>"
        + '<div class="road-th">' + (road.priority ? "PRIORITY ROAD" : "EXPANDED NETWORK") + "</div>"
        + '<div class="road-card-stats">'
        + '<div class="road-stat"><span>CONFIRMED INCIDENTS</span><strong>' + incidents + "</strong></div>"
        + '<div class="road-stat"><span>CURRENT SPEED</span><strong>—</strong></div>'
        + "</div>"
        + '<div class="road-card-note">'
        + (incidents ? "พบ incident ที่ยืนยันกับแนวถนนแล้ว" : "ยังไม่พบ incident ที่ยืนยันได้ใน feed ปัจจุบัน")
        + "<br>ความเร็วรายช่วงถนนยังไม่พร้อมใช้งาน"
        + "</div></article>";
    }).join("");
    document.querySelectorAll("[data-road-card]").forEach((card) => {
      card.addEventListener("click", () => selectRoad(card.dataset.roadCard));
    });
  }

  function updateMapSelection() {
    document.querySelectorAll(".network-road").forEach((el) => {
      const match = selectedRoad === "all" || el.dataset.road === selectedRoad;
      el.classList.toggle("is-muted", !match);
      el.classList.toggle("is-selected", selectedRoad !== "all" && el.dataset.road === selectedRoad);
    });
    document.querySelectorAll(".incident-point").forEach((el) => {
      el.classList.toggle("is-muted", selectedRoad !== "all" && el.dataset.road !== selectedRoad);
    });
  }

  function selectRoad(id) {
    selectedRoad = id === selectedRoad ? "all" : id;
    renderFilters();
    renderIncidents();
    renderRoadCards();
    updateMapSelection();
  }

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    safeStorageSet("bkkmi-theme", theme);
    if (networkData && statusData) {
      renderLegend();
      renderMap();
    }
  }

  function setupTheme() {
    const stored = safeStorageGet("bkkmi-theme");
    const preferred = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    applyTheme(stored || preferred);
    $("themeToggle").addEventListener("click", () => {
      applyTheme(document.documentElement.dataset.theme === "light" ? "dark" : "light");
    });
  }

  async function load() {
    try {
      setupTheme();
      const [statusRes, networkRes] = await Promise.all([
        fetch("data/latest_status.json", { cache: "no-store" }),
        fetch("data/core_roads.geojson", { cache: "no-store" })
      ]);
      if (!statusRes.ok || !networkRes.ok) throw new Error("data artifact not available");
      statusData = await statusRes.json();
      networkData = await networkRes.json();
      renderMetrics();
      renderLegend();
      renderMap();
      renderFilters();
      renderIncidents();
      renderRoadCards();
    } catch (error) {
      console.error(error);
      const banner = document.createElement("div");
      banner.className = "error-banner";
      banner.textContent = "ไม่สามารถโหลด dashboard data ได้: " + error.message;
      document.querySelector("main").prepend(banner);
      $("freshnessText").textContent = "Data load failed";
    }
  }

  load();
})();
