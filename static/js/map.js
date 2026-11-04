// OpenStreetMap map on the phone (Leaflet, stored on the phone). Shows the filtered GPS position,
// accuracy circle, heading arrow, walked trail, saved spots and a dashed line to the goal.
// Map tiles come from tile.openstreetmap.org; every tile seen once is kept by the service worker,
// so areas you have already looked at still show with no network. Without tiles the trail and
// points are still drawn (on a plain background).
// Tap the map to add a destination anywhere (not only where you have stood).
// Uses globals: $, L (Leaflet), nav, navPosition, navGoal, addWaypointAt, renderNav.

const osm = { map: null, follow: true, me: null, acc: null, trail: null, goalLine: null, wps: null, wpKey: "" };

function initMap() {
  if (osm.map || typeof L === "undefined") return !!osm.map;
  const p = navPosition();
  if (!p) return false;
  $("map").style.display = "block"; $("minimap").style.display = "none";
  osm.map = L.map("map", { zoomControl: true, attributionControl: true }).setView(p, 18);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, crossOrigin: true,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(osm.map);
  osm.trail = L.polyline([], { color: "#4c8dff", weight: 4 }).addTo(osm.map);
  osm.goalLine = L.polyline([], { color: "#ffd23f", weight: 3, dashArray: "8 8" }).addTo(osm.map);
  osm.acc = L.circle(p, { radius: 5, color: "#4c8dff", weight: 1, fillOpacity: 0.12 }).addTo(osm.map);
  osm.me = L.marker(p, { icon: L.divIcon({ className: "me-icon", iconSize: [28, 28], iconAnchor: [14, 14],
    html: '<svg viewBox="0 0 28 28" width="28" height="28"><path d="M14 2 L23 24 L14 19 L5 24 Z" fill="#e8ebf0" stroke="#0e1116" stroke-width="2"/></svg>' }),
    interactive: false }).addTo(osm.map);
  osm.wps = L.layerGroup().addTo(osm.map);
  // stop following when the user pans; the ⌖ button turns it back on
  osm.map.on("dragstart", () => { osm.follow = false; $("map-follow").style.opacity = 1; });
  osm.map.on("click", e => {
    const name = prompt("Add a destination here? Name:", `Point ${nav.waypoints.length + 1}`);
    if (name == null) return;
    addWaypointAt(e.latlng.lat, e.latlng.lng, name.trim());
    nav.goalIdx = nav.waypoints.length - 1;
    renderNav();
  });
  return true;
}

function updateMap() {
  if (!initMap()) return;
  const p = navPosition();
  if (!p) return;
  osm.me.setLatLng(p);
  const svg = osm.me.getElement()?.querySelector("svg");
  if (svg) svg.style.transform = `rotate(${nav.heading || 0}deg)`;
  osm.acc.setLatLng(p).setRadius(Math.max(2, nav.acc || state.gps?.acc || 5));
  if (osm.trail.getLatLngs().length !== nav.trail.length) osm.trail.setLatLngs(nav.trail);
  const key = JSON.stringify([nav.waypoints, nav.goalIdx]);
  if (key !== osm.wpKey) {                         // redraw saved points only when they change
    osm.wpKey = key; osm.wps.clearLayers();
    nav.waypoints.forEach((w, i) => {
      L.circleMarker([w.lat, w.lon], { radius: 7, color: "#0e1116", weight: 2,
        fillColor: i === nav.goalIdx ? "#ffd23f" : "#b07cff", fillOpacity: 1 })
        .bindTooltip(w.name, { permanent: true, direction: "right", className: "wp-tip" })
        .on("click", ev => { L.DomEvent.stopPropagation(ev); nav.goalIdx = i; renderNav(); })
        .addTo(osm.wps);
    });
  }
  const wp = nav.waypoints[nav.goalIdx];
  osm.goalLine.setLatLngs(wp ? [p, [wp.lat, wp.lon]] : []);
  if (osm.follow) osm.map.panTo(p, { animate: false });
}

$("map-follow").onclick = () => {
  osm.follow = true; $("map-follow").style.opacity = 0.5;
  const p = navPosition(); if (osm.map && p) osm.map.setView(p, Math.max(osm.map.getZoom(), 17));
};
$("map-fit").onclick = () => {
  if (!osm.map) return;
  const pts = [...nav.trail, ...nav.waypoints.map(w => [w.lat, w.lon])], p = navPosition();
  if (p) pts.push(p);
  if (pts.length > 1) { osm.follow = false; $("map-follow").style.opacity = 1; osm.map.fitBounds(pts, { padding: [30, 30], maxZoom: 19 }); }
};
