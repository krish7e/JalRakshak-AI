/**
 * JalRakshak AI — Node.js Zero-Dependency Server.
 * 
 * Uses Node.js v22 built-in `node:sqlite` and `node:http`.
 * Zero `npm install` needed. Runs directly out of the box!
 * 
 * Connects directly to the shared SQLite database: `backend/jalrakshak.db`
 * Serves index.html at http://localhost:3000/ and handles all REST API endpoints.
 * 
 * Run:
 *   node server.js       (or: npm start)
 */
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { DatabaseSync } = require('node:sqlite');

const PORT = parseInt(process.env.PORT || '3000', 10);
const DB_PATH = path.join(__dirname, 'backend', 'jalrakshak.db');
const INDEX_HTML_PATH = path.join(__dirname, 'index.html');

// Initialize SQLite connection
let db;
try {
  db = new DatabaseSync(DB_PATH);
  // Ensure WAL mode and tables
  db.exec(`
    CREATE TABLE IF NOT EXISTS districts (
      district TEXT PRIMARY KEY, state TEXT NOT NULL,
      lat REAL NOT NULL, lng REAL NOT NULL,
      farms INTEGER NOT NULL, base_depth REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS groundwater_weekly (
      district TEXT NOT NULL, week INTEGER NOT NULL,
      reading_date TEXT, depth_bgl REAL NOT NULL,
      PRIMARY KEY (district, week)
    );
    CREATE TABLE IF NOT EXISTS plots (
      id TEXT PRIMARY KEY, belt TEXT NOT NULL, district TEXT NOT NULL,
      state TEXT NOT NULL, owner TEXT NOT NULL, acres REAL NOT NULL,
      crop TEXT NOT NULL, stage TEXT NOT NULL, lat REAL NOT NULL,
      lng REAL NOT NULL, seed INTEGER NOT NULL DEFAULT 10,
      discharge REAL NOT NULL DEFAULT 18.0, runtime REAL NOT NULL DEFAULT 6.0,
      risk_level TEXT DEFAULT 'Normal'
    );
    CREATE TABLE IF NOT EXISTS tubewells (
      id TEXT PRIMARY KEY, plot_id TEXT, farmer_name TEXT NOT NULL,
      district TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'punjab',
      lat REAL NOT NULL, lng REAL NOT NULL, depth REAL NOT NULL,
      discharge_lps REAL NOT NULL, status TEXT NOT NULL DEFAULT 'IDLE',
      running_hours REAL NOT NULL DEFAULT 4.5, power_kw REAL NOT NULL DEFAULT 5.0,
      daily_extraction_kl REAL NOT NULL DEFAULT 81.0, feeder_window TEXT DEFAULT 'morning',
      last_updated TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS settings (
      key TEXT PRIMARY KEY, value TEXT NOT NULL
    );
  `);
} catch (err) {
  console.error('[ERROR] Failed to open SQLite database:', err.message);
}

// Helpers
function getCounts() {
  try {
    const d = db.prepare('SELECT COUNT(*) as c FROM districts').get().c;
    const g = db.prepare('SELECT COUNT(*) as c FROM groundwater_weekly').get().c;
    const p = db.prepare('SELECT COUNT(*) as c FROM plots').get().c;
    const t = db.prepare('SELECT COUNT(*) as c FROM tubewells').get().c;
    return { districts: d, readings: g, plots: p, tubewells: t };
  } catch (e) {
    return { districts: 0, readings: 0, plots: 0, tubewells: 0 };
  }
}

function stressLevel(depth) {
  if (depth > 30) return { level: 'high', color: '#ef4444', dotClass: 'red', label: 'High / Critical', statusLabel: 'Over-Exploited' };
  if (depth >= 20) return { level: 'elevated', color: '#f59e0b', dotClass: 'amber', label: 'Elevated', statusLabel: 'Critical' };
  return { level: 'normal', color: '#10b981', dotClass: 'green', label: 'Normal', statusLabel: 'Semi-Critical' };
}

function parseJsonBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch (err) {
        reject(err);
      }
    });
    req.on('error', reject);
  });
}

function sendJson(res, statusCode, data) {
  res.writeHead(statusCode, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization'
  });
  res.end(JSON.stringify(data));
}

// HTTP Server
const server = http.createServer(async (req, res) => {
  // CORS Preflight
  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization'
    });
    return res.end();
  }

  const parsedUrl = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  const pathname = parsedUrl.pathname;

  // Serve Frontend Dashboard
  if (pathname === '/' || pathname === '/index.html') {
    if (fs.existsSync(INDEX_HTML_PATH)) {
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      return fs.createReadStream(INDEX_HTML_PATH).pipe(res);
    }
    return sendJson(res, 404, { error: 'index.html not found' });
  }

  // --- API Endpoints ---
  try {
    // 1. Health
    if (pathname === '/api/health' && req.method === 'GET') {
      const counts = getCounts();
      return sendJson(res, 200, {
        status: 'ok',
        database: 'sqlite',
        runtime: 'Node.js ' + process.version,
        path: DB_PATH,
        ...counts
      });
    }

    // 2. Districts
    if (pathname === '/api/districts' && req.method === 'GET') {
      const state = parsedUrl.searchParams.get('state');
      let query = 'SELECT district, state, lat, lng, farms, base_depth as baseDepth FROM districts';
      const params = [];
      if (state && state !== 'all') {
        query += ' WHERE state = ?';
        params.push(state);
      }
      query += ' ORDER BY district';
      const rows = db.prepare(query).all(...params);
      return sendJson(res, 200, { count: rows.length, districts: rows });
    }

    // 3. Groundwater Latest
    if (pathname === '/api/groundwater/latest' && req.method === 'GET') {
      const districts = db.prepare('SELECT * FROM districts ORDER BY district').all();
      const rows = [];
      for (const d of districts) {
        const series = db.prepare(
          'SELECT week, reading_date as date, depth_bgl as depth FROM groundwater_weekly WHERE district = ? ORDER BY week ASC'
        ).all(d.district);
        if (!series || series.length === 0) continue;
        const latest = series[series.length - 1];
        const depth = latest.depth;
        const li = series.length - 1;
        const si = Math.max(0, li - 7);
        const velocity = Math.round(((series[li].depth - series[si].depth) / Math.max(1, li - si)) * 100) / 100;
        const stress = stressLevel(depth);
        const baseFactor = 8 + (depth / 30.0) * 12;
        const mult = stress.level === 'high' ? 1.4 : (stress.level === 'elevated' ? 1.15 : 1.0);
        rows.push({
          name: d.district,
          state: d.state,
          lat: d.lat,
          lng: d.lng,
          farms: d.farms,
          depth: depth,
          stress: stress,
          velocity: velocity,
          extraction: Math.round(baseFactor * mult * 10),
          projectedDepth8w: Math.round((depth + velocity * 8) * 100) / 100
        });
      }
      rows.sort((a, b) => b.depth - a.depth);
      return sendJson(res, 200, { week: 41, count: rows.length, districts: rows });
    }

    // 4. District One
    if (pathname.startsWith('/api/groundwater/') && req.method === 'GET') {
      const districtName = decodeURIComponent(pathname.replace('/api/groundwater/', ''));
      const meta = db.prepare('SELECT * FROM districts WHERE district = ?').get(districtName);
      if (!meta) return sendJson(res, 404, { detail: `Unknown district: ${districtName}` });
      const series = db.prepare(
        'SELECT week, reading_date as date, depth_bgl as depth FROM groundwater_weekly WHERE district = ? ORDER BY week ASC'
      ).all(districtName);
      if (!series || series.length === 0) return sendJson(res, 404, { detail: `No series found for ${districtName}` });
      const depth = series[series.length - 1].depth;
      const li = series.length - 1;
      const si = Math.max(0, li - 7);
      const velocity = Math.round(((series[li].depth - series[si].depth) / Math.max(1, li - si)) * 100) / 100;
      return sendJson(res, 200, {
        district: districtName,
        meta: meta,
        latest: series[series.length - 1],
        stress: stressLevel(depth),
        velocity: velocity,
        series: series
      });
    }

    // 5. POST Reading
    if (pathname.startsWith('/api/groundwater/') && req.method === 'POST') {
      const districtName = decodeURIComponent(pathname.replace('/api/groundwater/', ''));
      const body = await parseJsonBody(req);
      db.prepare(`
        INSERT INTO groundwater_weekly (district, week, reading_date, depth_bgl)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(district, week) DO UPDATE SET reading_date=excluded.reading_date, depth_bgl=excluded.depth_bgl
      `).run(districtName, parseInt(body.week, 10), body.date || null, parseFloat(body.depthBgl));
      return sendJson(res, 200, { ok: true, district: districtName, item: body });
    }

    // 6. Farm Plots (Registry)
    if (pathname === '/api/registry/plots') {
      if (req.method === 'GET') {
        const district = parsedUrl.searchParams.get('district');
        const state = parsedUrl.searchParams.get('state');
        let q = 'SELECT * FROM plots WHERE 1=1';
        const params = [];
        if (district && district !== 'all') { q += ' AND district = ?'; params.push(district); }
        if (state && state !== 'all') { q += ' AND state = ?'; params.push(state); }
        q += ' ORDER BY id';
        const rows = db.prepare(q).all(...params).map(r => ({
          ...r,
          center: [r.lat, r.lng],
          riskLevel: r.risk_level || 'Normal'
        }));
        return sendJson(res, 200, { count: rows.length, plots: rows });
      }

      if (req.method === 'POST') {
        const p = await parseJsonBody(req);
        if (!p.id) {
          const count = db.prepare('SELECT COUNT(*) as c FROM plots').get().c + 1;
          const prefix = (p.district ? p.district.slice(0, 3) : 'PLT').toUpperCase();
          p.id = `${prefix}-${String(count).padStart(2, '0')}`;
        }
        const lat = p.center ? p.center[0] : (p.lat || 30.0);
        const lng = p.center ? p.center[1] : (p.lng || 75.0);
        db.prepare(`
          INSERT INTO plots (id, belt, district, state, owner, acres, crop, stage, lat, lng, seed, discharge, runtime, risk_level)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
          ON CONFLICT(id) DO UPDATE SET
            belt=excluded.belt, district=excluded.district, state=excluded.state,
            owner=excluded.owner, acres=excluded.acres, crop=excluded.crop,
            stage=excluded.stage, lat=excluded.lat, lng=excluded.lng,
            seed=excluded.seed, discharge=excluded.discharge, runtime=excluded.runtime,
            risk_level=excluded.risk_level
        `).run(
          p.id, p.belt || p.district, p.district, p.state, p.owner,
          parseFloat(p.acres), p.crop, p.stage, lat, lng,
          parseInt(p.seed || 10, 10), parseFloat(p.discharge || 18.0),
          parseFloat(p.runtime || 6.0), p.riskLevel || 'Normal'
        );
        return sendJson(res, 200, { ok: true, plot: p });
      }
    }

    if (pathname.startsWith('/api/registry/plots/') && req.method === 'DELETE') {
      const plotId = decodeURIComponent(pathname.replace('/api/registry/plots/', ''));
      db.prepare('DELETE FROM plots WHERE id = ?').run(plotId);
      return sendJson(res, 200, { ok: true, deleted: plotId });
    }

    // 7. Tubewells
    if (pathname === '/api/tubewells' && req.method === 'GET') {
      const rows = db.prepare('SELECT * FROM tubewells ORDER BY id').all().map(r => ({
        id: r.id,
        plotId: r.plot_id,
        farmerName: r.farmer_name,
        district: r.district,
        state: r.state,
        lat: r.lat,
        lng: r.lng,
        depth: r.depth,
        dischargeLps: r.discharge_lps,
        status: r.status,
        runningHours: r.running_hours,
        powerKw: r.power_kw,
        dailyExtractionKl: r.daily_extraction_kl,
        feederWindow: r.feeder_window,
        lastUpdated: r.last_updated
      }));
      return sendJson(res, 200, { count: rows.length, tubewells: rows });
    }

    if (pathname.includes('/toggle') && pathname.startsWith('/api/tubewells/')) {
      const parts = pathname.split('/');
      const twId = parts[3];
      const cur = db.prepare('SELECT status FROM tubewells WHERE id = ?').get(twId);
      if (!cur) return sendJson(res, 404, { error: 'Tubewell not found' });
      const newStatus = cur.status === 'RUNNING' ? 'IDLE' : 'RUNNING';
      db.prepare("UPDATE tubewells SET status = ?, last_updated = datetime('now') WHERE id = ?").run(newStatus, twId);
      return sendJson(res, 200, { ok: true, id: twId, status: newStatus });
    }

    // 8. Irrigation Planner
    if (pathname === '/api/planner/calculate' && req.method === 'GET') {
      const crop = parsedUrl.searchParams.get('crop') || 'Paddy';
      const stage = parsedUrl.searchParams.get('stage') || 'Mid-season';
      const acres = parseFloat(parsedUrl.searchParams.get('acres') || '5.0');
      const depth = parseFloat(parsedUrl.searchParams.get('depth') || '25.0');
      const discharge = parseFloat(parsedUrl.searchParams.get('discharge') || '18.0');

      const kcTable = {
        Paddy: { Initial: 0.60, Development: 0.85, 'Mid-season': 1.05, Late: 0.85 },
        Wheat: { Initial: 0.40, Development: 0.75, 'Mid-season': 1.10, Late: 0.45 },
        Maize: { Initial: 0.40, Development: 0.75, 'Mid-season': 1.15, Late: 0.60 },
        Cotton: { Initial: 0.35, Development: 0.70, 'Mid-season': 1.15, Late: 0.70 },
        Sugarcane: { Initial: 0.40, Development: 0.75, 'Mid-season': 1.25, Late: 0.75 }
      };
      const kc = (kcTable[crop] && kcTable[crop][stage]) || 0.90;
      const etc = 5.5 * kc;
      const stressMult = depth > 30 ? 1.3 : (depth >= 20 ? 1.15 : 1.0);
      const volCum = Math.round(((etc * stressMult) / 1000.0) * (acres * 4046.86) * 10) / 10;
      const optHours = Math.round((volCum / Math.max(1.0, discharge)) * 10) / 10;
      const convHours = Math.round((optHours * 1.35) * 10) / 10;
      const savedCum = Math.round((convHours - optHours) * discharge * 10) / 10;

      return sendJson(res, 200, {
        crop, stage, acres, depthBgl: depth, pumpCapacityM3h: discharge,
        kc, waterRequirementM3: volCum, recommendedRuntimeHours: optHours,
        conventionalRuntimeHours: convHours, dailyWaterSavingsM3: savedCum,
        recommendedFeederWindow: 'Morning (05:00 AM - 09:00 AM)'
      });
    }

    // 9. Settings
    if (pathname === '/api/settings') {
      if (req.method === 'GET') {
        const rows = db.prepare('SELECT key, value FROM settings').all();
        const settings = {};
        for (const r of rows) {
          try { settings[r.key] = JSON.parse(r.value); }
          catch (e) { settings[r.key] = r.value; }
        }
        return sendJson(res, 200, settings);
      }
      if (req.method === 'POST') {
        const body = await parseJsonBody(req);
        for (const [k, v] of Object.entries(body)) {
          const valStr = typeof v === 'object' ? JSON.stringify(v) : String(v);
          db.prepare('INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value').run(k, valStr);
        }
        return sendJson(res, 200, { ok: true, settings: body });
      }
    }

    return sendJson(res, 404, { error: 'Not Found', path: pathname });
  } catch (err) {
    console.error('[API ERROR]', err);
    return sendJson(res, 500, { error: err.message });
  }
});

server.listen(PORT, () => {
  const counts = getCounts();
  console.log(`=======================================================`);
  console.log(`JalRakshak AI Node.js Backend is running!`);
  console.log(`URL: http://localhost:${PORT}`);
  console.log(`Database: SQLite (${DB_PATH})`);
  console.log(`Loaded: ${counts.districts} districts, ${counts.readings} readings, ${counts.plots} plots, ${counts.tubewells} tubewells`);
  console.log(`=======================================================`);
});
