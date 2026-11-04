// On-phone recorder: every session is kept in the phone's IndexedDB (survives reloads and works
// with no network). 2 samples a second; export as CSV / JSON or upload to the Mac when it is around.
// Uses globals: $, f, state, nav, navGoal, settings.

const REC = { db: null, session: null, buf: [], timer: null, count: 0, lastSample: 0 };
const REC_FIELDS = ["t", "lat", "lon", "acc", "speed", "heading", "pitch", "action", "cmdHeading", "steer",
                    "throttle", "clear", "ahead", "nearDist", "nearAngle", "obstacles", "free", "ttc", "flowTurn", "pathSrc", "goal", "goalDist", "fps"];

function recOpen() {
  if (REC.db) return Promise.resolve(REC.db);
  return new Promise((res, rej) => {
    const r = indexedDB.open("rover-log", 1);
    r.onupgradeneeded = () => {
      const db = r.result;
      db.createObjectStore("sessions", { keyPath: "id" });
      db.createObjectStore("samples", { autoIncrement: true }).createIndex("session", "session");
    };
    r.onsuccess = () => { REC.db = r.result; res(REC.db); };
    r.onerror = () => rej(r.error);
  });
}
const recTx = (stores, mode, fn) => recOpen().then(db => new Promise((res, rej) => {
  const tx = db.transaction(stores, mode); let out;
  tx.oncomplete = () => res(out); tx.onerror = () => rej(tx.error);
  out = fn(tx);
}));
const reqP = r => new Promise((res, rej) => { r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });

async function recStart() {
  if (REC.session) return;
  navigator.storage?.persist?.().catch(() => {});        // ask the browser not to evict the log
  const d = new Date(), id = d.toISOString().replace(/[-:]/g, "").slice(0, 15);
  REC.session = { id, start: d.getTime(), end: null, samples: 0,
                  setup: { camera: state.camera, camH: settings.camH, fov: settings.fov,
                           pitchOffset: settings.pitchOffset, fov: settings.fov, accBias: settings.accBias, gyroBias: settings.gyroBias,
                           compassOffset: settings.compassOffset, gpsMaxAcc: settings.gpsMaxAcc, edgeMargin: settings.edgeMargin, edgeSens: settings.edgeSens, pathMode: settings.pathMode, model: settings.model } };
  REC.count = 0; REC.buf = [];
  await recTx(["sessions"], "readwrite", tx => tx.objectStore("sessions").put(REC.session));
  REC.timer = setInterval(recFlush, 2000);
}

async function recStop() {
  if (!REC.session) return;
  clearInterval(REC.timer);
  await recFlush();
  REC.session.end = Date.now(); REC.session.samples = REC.count;
  await recTx(["sessions"], "readwrite", tx => tx.objectStore("sessions").put(REC.session));
  REC.session = null;
}

// Called every frame; keeps 2 samples/second.
function recSample() {
  if (!REC.session || performance.now() - REC.lastSample < 500) return;
  REC.lastSample = performance.now();
  const d = state.decision || {}, near = state.obstacles[0], g = navGoal();
  const r = v => v == null || isNaN(v) ? null : +(+v).toFixed(2);
  REC.buf.push({ session: REC.session.id, t: Date.now(),
    lat: nav.lat == null ? null : +nav.lat.toFixed(7), lon: nav.lon == null ? null : +nav.lon.toFixed(7),
    acc: r(nav.acc), speed: r(nav.speed), heading: r(nav.heading), pitch: r(state.pitch),
    action: d.action || null, cmdHeading: r(d.heading), steer: r(d.steer), throttle: r(d.throttle),
    clear: r(d.clear), ahead: r(d.ahead), nearDist: r(near?.dist), nearAngle: r(near?.angle),
    obstacles: state.obstacles.length, free: r(state.path?.freeFrac), ttc: r(state.ttc),
    flowTurn: r(cvs.flow?.turn), pathSrc: state.path?.source || null,
    goal: g?.name || null, goalDist: r(g?.dist), fps: state.fps });
  REC.count++;
}

async function recFlush() {
  if (!REC.buf.length) return;
  const batch = REC.buf; REC.buf = [];
  await recTx(["samples", "sessions"], "readwrite", tx => {
    const s = tx.objectStore("samples");
    for (const x of batch) s.add(x);
    if (REC.session) { REC.session.samples = REC.count; tx.objectStore("sessions").put(REC.session); }
  });
}

const recSessions = () => recTx(["sessions"], "readonly", tx => reqP(tx.objectStore("sessions").getAll()));
const recSamples = id => recTx(["samples"], "readonly",
  tx => reqP(tx.objectStore("samples").index("session").getAll(IDBKeyRange.only(id))));

async function recDelete(id) {
  const keys = await recTx(["samples"], "readonly",
    tx => reqP(tx.objectStore("samples").index("session").getAllKeys(IDBKeyRange.only(id))));
  await recTx(["samples", "sessions"], "readwrite", tx => {
    const s = tx.objectStore("samples"); keys.forEach(k => s.delete(k));
    tx.objectStore("sessions").delete(id);
  });
}

function toCSV(rows) {
  const esc = v => v == null ? "" : /[",\n]/.test(v) ? `"${String(v).replace(/"/g, '""')}"` : v;
  return [REC_FIELDS.join(","), ...rows.map(x => REC_FIELDS.map(k => esc(k === "t" ? new Date(x.t).toISOString() : x[k])).join(","))].join("\n");
}

async function recExport(id, kind) {
  const [sessions, rows] = await Promise.all([recSessions(), recSamples(id)]);
  const sess = sessions.find(s => s.id === id);
  const text = kind === "csv" ? toCSV(rows) : JSON.stringify({ session: sess, fields: REC_FIELDS, samples: rows });
  const name = `rover_${id}.${kind}`, type = kind === "csv" ? "text/csv" : "application/json";
  if (IS_APK) {                                           // Android app: straight into Downloads
    const where = AndroidBridge.saveFile(name, type, text);
    if (where.startsWith("ERROR")) throw new Error(where.slice(6));
    return "saved to " + where;
  }
  const file = new File([text], name, { type });
  if (navigator.canShare?.({ files: [file] })) {          // Android share sheet: Drive, email, Files...
    try { await navigator.share({ files: [file], title: name }); return "shared"; } catch (e) { if (e.name === "AbortError") return "cancelled"; }
  }
  const a = document.createElement("a");                  // fallback: download into the phone's Downloads
  a.href = URL.createObjectURL(file); a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 10000);
  return "downloaded";
}

async function recUpload(id) {
  const [sessions, rows] = await Promise.all([recSessions(), recSamples(id)]);
  const res = await fetch("api/upload", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session: sessions.find(s => s.id === id), fields: REC_FIELDS, samples: rows }) });
  if (!res.ok) throw new Error("HTTP " + res.status);
  return (await res.json()).file;
}

// ---------- UI ----------
let recRenderId = 0;
async function recRender() {
  const box = $("rec-list"), my = ++recRenderId;      // overlapping refreshes: only the newest draws
  let list;
  try { list = (await recSessions()).sort((a, b) => b.start - a.start); }
  catch (e) { box.innerHTML = `<p class="hint">Storage not available: ${e.message}</p>`; return; }
  const est = await navigator.storage?.estimate?.().catch(() => null);
  if (my !== recRenderId) return;
  $("rec-store").textContent = est ? `${(est.usage / 1e6).toFixed(1)} MB used on the phone` : "";
  box.innerHTML = list.length ? "" : `<p class="hint">No recordings yet.</p>`;
  for (const s of list) {
    const live = REC.session?.id === s.id, dur = ((s.end || Date.now()) - s.start) / 1000;
    const row = document.createElement("div"); row.className = "rec-row";
    row.innerHTML = `<div><b>${new Date(s.start).toLocaleString()}</b>${live ? ' <span style="color:var(--stop)">● recording</span>' : ""}
      <div class="hint">${Math.floor(dur / 60)} min ${Math.round(dur % 60)} s · ${live ? REC.count : s.samples} samples</div></div>
      <div class="row">${live ? "" : `<button data-a="csv">CSV</button><button data-a="json">JSON</button>
      ${IS_APK ? "" : '<button data-a="up">To Mac</button>'}<button data-a="del" class="danger">Delete</button>`}</div>`;
    row.onclick = async e => {
      const a = e.target.dataset?.a; if (!a) return;
      const msg = $("rec-msg");
      try {
        if (a === "del") { if (!confirm("Delete this recording from the phone?")) return; await recDelete(s.id); msg.textContent = "Deleted."; }
        else if (a === "up") { msg.textContent = "Uploading…"; msg.textContent = "Saved on the Mac: " + await recUpload(s.id); }
        else msg.textContent = `${a.toUpperCase()}: ${await recExport(s.id, a)}`;
      } catch (err) { msg.textContent = a === "up" ? "Mac not reachable — export CSV instead." : "Failed: " + err.message; }
      recRender();
    };
    box.appendChild(row);
  }
}
