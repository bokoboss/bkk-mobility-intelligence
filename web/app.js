(() => {
  "use strict";

  const PRIORITY_COLORS = {
    ram_inthra: "#4cc9f0",
    prasert_manukitch: "#65d49a",
    pradit_manutham: "#f0b55a",
    nuan_chan: "#b89cff"
  };

  const OPENFREEMAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";

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
  let historyData = null;
  let selectedRoad = "all";
  let activeWindow = "now";
  let map = null;
  let mapReady = false;

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

  function windowIncidents(windowId = activeWindow) {
    if (windowId === "now") return allIncidents();
    return [...(historyData?.windows?.[windowId]?.clusters || [])]
      .sort((a, b) => String(b.latest_start || "").localeCompare(String(a.latest_start || "")));
  }

  function windowRoadCount(roadId, windowId = activeWindow) {
    return windowIncidents(windowId).filter((item) => item.road_id === roadId).length;
  }

  function displayWindowLabel() {
    if (activeWindow === "7d") return "7 วันล่าสุด";
    if (activeWindow === "30d") return "30 วันล่าสุด";
    return "ตอนนี้";
  }

  function priorityRoadIds() {
    return Object.entries(statusData?.roads || {})
      .filter(([, road]) => road.priority)
      .map(([id]) => id);
  }

  function incidentRoadIds(windowId = activeWindow) {
    const counts = {};
    windowIncidents(windowId).forEach((item) => {
      if (item.road_id) counts[item.road_id] = (counts[item.road_id] || 0) + 1;
    });
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .map(([id]) => id);
  }

  function renderHistorySummary() {
    if (!historyData) return;
    const w7 = historyData.windows?.["7d"] || {};
    const w30 = historyData.windows?.["30d"] || {};
    const trend = historyData.trend || {};

    $("history7Count").textContent = w7.incident_count ?? "—";
    $("history7Roads").textContent = "บน " + (w7.road_count ?? "—") + " ถนน";
    $("history30Count").textContent = w30.incident_count ?? "—";
    $("history30Roads").textContent = "บน " + (w30.road_count ?? "—") + " ถนน";

    const change = trend.absolute_change;
    const pct = trend.percent_change;
    $("historyTrend").textContent = change == null
      ? "—"
      : (change > 0 ? "+" : "") + change + (pct == null ? "" : " (" + (pct > 0 ? "+" : "") + pct + "%)");
    $("historyPriorCount").textContent = "7 วันก่อนหน้า " + (trend.prior_7d_count ?? "—") + " เหตุ";

    const renderRank = (id, rows) => {
      $(id).innerHTML = (rows || []).slice(0, 5).map((row) =>
        '<div class="history-rank-row"><span>' + escapeHtml(row.label) + '</span><strong>' + row.count + '</strong></div>'
      ).join("") || '<div class="empty-list">ยังไม่มีข้อมูล</div>';
    };
    renderRank("historyTopRoads", w30.top_roads);
    renderRank("historyTopTypes", w30.top_event_types);
  }

  function renderWindowControls() {
    document.querySelectorAll("[data-window]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.window === activeWindow);
    });
    $("incidentPanelTitle").textContent = "เหตุที่ยืนยันได้ · " + displayWindowLabel();
  }

  function setWindow(windowId) {
    if (!["now", "7d", "30d"].includes(windowId)) return;
    activeWindow = windowId;
    selectedRoad = "all";
    renderWindowControls();
    renderFilters();
    renderIncidents();
    renderRoadCards();
    updateIncidentMapSource();
    updateMapSelection();
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
    priority.push('<div class="legend-item"><span class="legend-dot"></span>เหตุที่ยืนยันได้</div>');
    $("mapLegend").innerHTML = priority.join("");
  }

  function incidentGeoJSON() {
    return {
      type: "FeatureCollection",
      features: windowIncidents()
        .filter((incident) => Number.isFinite(Number(incident.longitude)) && Number.isFinite(Number(incident.latitude)))
        .map((incident) => ({
          type: "Feature",
          geometry: {
            type: "Point",
            coordinates: [Number(incident.longitude), Number(incident.latitude)]
          },
          properties: {
            road_id: incident.road_id,
            road_name: roadLabel(incident.road_id),
            title: incident.title || "เหตุการณ์",
            latest_start: incident.latest_start || "",
            event_type: incident.event_type || "",
            record_count: incident.record_count || 1,
            cluster_scope: incident.cluster_scope || ""
          }
        }))
    };
  }

  function updateIncidentMapSource() {
    if (!map || !mapReady) return;
    const source = map.getSource("confirmed-incidents");
    if (source) source.setData(incidentGeoJSON());

    if (map.getLayer("confirmed-incidents")) {
      const color = activeWindow === "now" ? cssVar("--danger") : activeWindow === "7d" ? "#f59e0b" : "#7c6cff";
      map.setPaintProperty("confirmed-incidents", "circle-color", color);
      map.setPaintProperty("confirmed-incidents", "circle-opacity", activeWindow === "now" ? 0.94 : 0.72);
      map.setPaintProperty(
        "confirmed-incidents",
        "circle-radius",
        ["interpolate", ["linear"], ["zoom"], 9, activeWindow === "now" ? 5 : 4, 14, activeWindow === "now" ? 8 : 6]
      );
    }
  }

  function roadColorExpression() {
    return [
      "match", ["get", "road_id"],
      "ram_inthra", PRIORITY_COLORS.ram_inthra,
      "prasert_manukitch", PRIORITY_COLORS.prasert_manukitch,
      "pradit_manutham", PRIORITY_COLORS.pradit_manutham,
      "nuan_chan", PRIORITY_COLORS.nuan_chan,
      cssVar("--subtle")
    ];
  }

  function studyBounds() {
    const b = statusData?.study_area_bbox_wgs84;
    if (b && Number.isFinite(Number(b.min_lon))) {
      return [[Number(b.min_lon), Number(b.min_lat)], [Number(b.max_lon), Number(b.max_lat)]];
    }

    const coords = [];
    (networkData?.features || []).forEach((feature) => {
      const geom = feature.geometry || {};
      const lines = geom.type === "MultiLineString" ? geom.coordinates : [geom.coordinates || []];
      lines.forEach((line) => line.forEach((p) => coords.push(p)));
    });
    if (!coords.length) return [[100.57, 13.755], [100.79, 13.93]];
    const lons = coords.map((p) => Number(p[0]));
    const lats = coords.map((p) => Number(p[1]));
    return [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]];
  }

  function fitStudyArea() {
    if (!map) return;
    map.fitBounds(studyBounds(), {
      padding: window.innerWidth < 720 ? 34 : 58,
      duration: 650,
      maxZoom: 13.2
    });
  }

  function addMapLayers() {
    if (!map || !networkData || !statusData) return;

    map.addSource("road-network", { type: "geojson", data: networkData });
    map.addLayer({
      id: "road-network",
      type: "line",
      source: "road-network",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": roadColorExpression(),
        "line-width": ["case", ["==", ["get", "priority"], true], 4.6, 2.4],
        "line-opacity": 0.72
      }
    });

    map.addLayer({
      id: "road-selected",
      type: "line",
      source: "road-network",
      filter: ["==", ["get", "road_id"], "__none__"],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": cssVar("--text"),
        "line-width": 7.5,
        "line-opacity": 0.95
      }
    });

    map.addSource("confirmed-incidents", { type: "geojson", data: incidentGeoJSON() });
    map.addLayer({
      id: "confirmed-incidents",
      type: "circle",
      source: "confirmed-incidents",
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 9, 5, 14, 8],
        "circle-color": cssVar("--danger"),
        "circle-stroke-color": "#ffffff",
        "circle-stroke-width": 1.8,
        "circle-opacity": 0.94
      }
    });

    map.on("click", (e) => {
      const features = map.queryRenderedFeatures(e.point, {
        layers: ["confirmed-incidents", "road-network"]
      });
      const feature = features[0];
      if (!feature) return;

      if (feature.layer.id === "confirmed-incidents") {
        const props = feature.properties || {};
        const coords = feature.geometry.coordinates.slice();
        selectedRoad = String(props.road_id || "all");
        renderFilters();
        renderIncidents();
        renderRoadCards();
        updateMapSelection();
        new maplibregl.Popup({ closeButton: true, maxWidth: "320px" })
          .setLngLat(coords)
          .setHTML(
            '<div class="map-popup-title">' + escapeHtml(props.title || "เหตุการณ์") + '</div>'
            + '<div class="map-popup-meta">' + escapeHtml(props.road_name || "") + '</div>'
            + '<div class="map-popup-meta">' + escapeHtml(formatThaiDate(props.latest_start)) + '</div>'
          )
          .addTo(map);
        return;
      }

      const roadId = feature.properties?.road_id;
      if (roadId) selectRoad(String(roadId));
    });

    map.on("mousemove", (e) => {
      const features = map.queryRenderedFeatures(e.point, {
        layers: ["confirmed-incidents", "road-network"]
      });
      map.getCanvas().style.cursor = features.length ? "pointer" : "";
    });

    mapReady = true;
    updateIncidentMapSource();
    updateMapSelection();
    fitStudyArea();
    $("mapLoading").hidden = true;
  }

  function initMap() {
    if (!window.maplibregl) {
      $("mapLoading").hidden = false;
      $("mapLoading").textContent = "โหลด MapLibre ไม่สำเร็จ — analytical data ยังอยู่ครบ แต่ basemap ใช้งานไม่ได้";
      return;
    }

    map = new maplibregl.Map({
      container: "interactiveMap",
      style: OPENFREEMAP_STYLE,
      center: [100.68, 13.84],
      zoom: 10.7,
      minZoom: 8,
      maxZoom: 18,
      attributionControl: true
    });

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    map.addControl(new maplibregl.FullscreenControl(), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric", maxWidth: 120 }), "bottom-left");

    map.on("load", addMapLayers);
    map.on("error", (event) => {
      if (event?.error) console.warn("MapLibre/OpenFreeMap error", event.error);
    });

    $("fitAreaButton").addEventListener("click", fitStudyArea);
    document.querySelectorAll("[data-window]").forEach((button) => {
      button.addEventListener("click", () => setWindow(button.dataset.window));
    });
  }

  function filterRoadIds() {
    const ids = [...priorityRoadIds()];
    incidentRoadIds().forEach((id) => { if (!ids.includes(id)) ids.push(id); });
    if (selectedRoad !== "all" && !ids.includes(selectedRoad)) ids.push(selectedRoad);
    return ids;
  }

  function renderFilters() {
    const chips = [
      { id: "all", label: "ทั้งหมด", count: allIncidents().length },
      ...filterRoadIds().map((id) => ({
        id,
        label: roadLabel(id).replace("ถนน", ""),
        count: windowRoadCount(id)
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
    const incidents = windowIncidents().filter((x) => selectedRoad === "all" || x.road_id === selectedRoad);
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
    const ids = [...priority, ...active.slice(0, 8)];
    if (selectedRoad !== "all" && !ids.includes(selectedRoad)) ids.push(selectedRoad);
    return ids;
  }

  function renderRoadCards() {
    $("roadCards").innerHTML = cardRoadIds().map((id) => {
      const road = roadMeta(id);
      const incidentsNow = road.confirmed_incident_count || 0;
      const incidents7d = windowRoadCount(id, "7d");
      const selected = selectedRoad === id ? " is-selected" : "";
      return '<article class="road-card' + selected + '" data-road-card="' + id
        + '" style="--road-color:' + roadColor(id) + '">'
        + '<div class="road-card-line"></div>'
        + "<h3>" + escapeHtml(road.display_name || id) + "</h3>"
        + '<div class="road-th">' + (road.priority ? "PRIORITY ROAD" : "EXPANDED NETWORK") + "</div>"
        + '<div class="road-card-stats">'
        + '<div class="road-stat"><span>NOW INCIDENTS</span><strong>' + incidentsNow + "</strong></div>"
        + '<div class="road-stat"><span>LAST 7 DAYS</span><strong>' + incidents7d + "</strong></div>'
        + "</div>"
        + '<div class="road-card-note">'
        + (incidentsNow ? "พบ incident ที่ยืนยันกับแนวถนนใน feed ปัจจุบัน" : "ยังไม่พบ incident ปัจจุบันที่ยืนยันได้")
        + "<br>Segment speed ยังไม่พร้อมใช้งาน"
        + "</div></article>";
    }).join("");
    document.querySelectorAll("[data-road-card]").forEach((card) => {
      card.addEventListener("click", () => selectRoad(card.dataset.roadCard));
    });
  }

  function updateMapSelection() {
    if (!map || !mapReady || !map.getLayer("road-network")) return;

    if (selectedRoad === "all") {
      map.setFilter("road-selected", ["==", ["get", "road_id"], "__none__"]);
      map.setPaintProperty("road-network", "line-opacity", 0.72);
      map.setPaintProperty("confirmed-incidents", "circle-opacity", activeWindow === "now" ? 0.94 : 0.72);
    } else {
      map.setFilter("road-selected", ["==", ["get", "road_id"], selectedRoad]);
      map.setPaintProperty(
        "road-network",
        "line-opacity",
        ["case", ["==", ["get", "road_id"], selectedRoad], 0.45, 0.14]
      );
      map.setPaintProperty(
        "confirmed-incidents",
        "circle-opacity",
        ["case", ["==", ["get", "road_id"], selectedRoad], activeWindow === "now" ? 0.98 : 0.82, 0.14]
      );
      map.setPaintProperty("road-selected", "line-color", roadColor(selectedRoad));
    }
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
    if (statusData) renderLegend();
    if (map && mapReady && map.getLayer("road-network")) {
      map.setPaintProperty("road-network", "line-color", roadColorExpression());
      updateIncidentMapSource();
      if (selectedRoad !== "all") {
        map.setPaintProperty("road-selected", "line-color", roadColor(selectedRoad));
      }
    }
    if (map) setTimeout(() => map.resize(), 0);
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
      const [statusRes, networkRes, historyRes] = await Promise.all([
        fetch("data/latest_status.json", { cache: "no-store" }),
        fetch("data/core_roads.geojson", { cache: "no-store" }),
        fetch("data/recent_incident_intelligence.json", { cache: "no-store" })
      ]);
      if (!statusRes.ok || !networkRes.ok || !historyRes.ok) throw new Error("data artifact not available");
      statusData = await statusRes.json();
      networkData = await networkRes.json();
      historyData = await historyRes.json();
      renderMetrics();
      renderHistorySummary();
      renderLegend();
      renderWindowControls();
      renderFilters();
      renderIncidents();
      renderRoadCards();
      initMap();
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
