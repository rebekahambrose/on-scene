// Shared by every page: data loading, icons, navigation, footer, small helpers.
(function () {
  const RAW = "https://raw.githubusercontent.com/rebekahambrose/on-scene/data/";
  const LOCAL = ["localhost", "127.0.0.1", ""].includes(location.hostname);
  const url = name => (LOCAL ? "data/" : RAW) + name + "?t=" + Date.now();
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const parseGen = iso => Date.parse(iso.replace("Z", ":00Z"));
  const ago = iso => {
    const m = Math.round((Date.now() - parseGen(iso)) / 60000);
    return m < 1 ? "just now" : m < 60 ? `${m} min ago` : m < 1440 ? `${Math.round(m / 60)} hr ago` : `${Math.round(m / 1440)} days ago`;
  };

  // ---------- icons: white symbol on a colored badge ----------
  const GLYPH = {
    ambulance: `<path d="M12 23h24v19H12z"/><path d="M36 29h8l7 7v6H36z"/><circle cx="20" cy="44" r="4.5"/><circle cx="43" cy="44" r="4.5"/><path d="M22.5 26.5h3v4h4v3h-4v4h-3v-4h-4v-3h4z" fill="C"/>`,
    car: `<path d="M12 41v-7l5-9h30l5 9v7z"/><path d="M20 27h24l3 6H17z" fill="C"/><circle cx="20" cy="43" r="4.5"/><circle cx="44" cy="43" r="4.5"/>`,
    flame: `<path d="M32 11c4 8 13 12 13 25 0 9-6 15-13 15s-13-6-13-15c0-6 4-9 6-15 1 6 4 8 6 8-1-6-1-12 1-18z"/>`,
    ring: `<circle cx="32" cy="32" r="13" fill="none" stroke="#fff" stroke-width="8"/><path d="M27 17h10v8H27zM27 39h10v8H27zM17 27h8v10h-8zM39 27h8v10h-8z" fill="C"/>`,
    alert: `<rect x="28.5" y="15" width="7" height="22" rx="3.5"/><circle cx="32" cy="45" r="4"/>`,
    heli: `<circle cx="32" cy="27" r="17" fill="none" stroke="#fff" stroke-width="2" opacity=".55"/><path d="M15 27h34M32 10v34" stroke="#fff" stroke-width="2.6" stroke-linecap="round"/><ellipse cx="32" cy="29" rx="6.5" ry="10"/><rect x="30.5" y="37" width="3" height="16" rx="1.5"/><rect x="26" y="50" width="12" height="3" rx="1.5"/>`,
    plane: `<path d="M32 9c2 0 3.5 2 3.5 5v12l15 9v4.5l-15-5v11l5 4v3.5L32 51l-8.5 2v-3.5l5-4v-11l-15 5V35l15-9V14c0-3 1.5-5 3.5-5z"/>`,
    football: `<g transform="rotate(-35 32 32)"><ellipse cx="32" cy="32" rx="19" ry="11.5"/><g stroke="C" stroke-width="2.4" stroke-linecap="round"><path d="M24 32h16M27 28.5v7M32 28.5v7M37 28.5v7"/></g></g>`,
    basketball: `<circle cx="32" cy="32" r="17"/><g fill="none" stroke="C" stroke-width="2.4"><path d="M15 32h34M32 15v34"/><path d="M20 20c5 5 5 19 0 24M44 20c-5 5-5 19 0 24"/></g>`,
    stadium: `<ellipse cx="32" cy="34" rx="20" ry="11"/><ellipse cx="32" cy="34" rx="12" ry="5.5" fill="C"/><path d="M14 26l4-9M50 26l-4-9M32 23v-9" stroke="#fff" stroke-width="2.6" stroke-linecap="round"/><path d="M28 31.5h8v5h-8z" fill="#fff" opacity=".8"/>`,
    cross: `<path d="M27 14h10v13h13v10H37v13H27V37H14V27h13z"/>`,
    quake: `<path d="M10 33h9l4-12 7 22 6-26 5 21 3-5h10" fill="none" stroke="#fff" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>`,
    bolt: `<path d="M37 10 21 36h10l-5 18 18-27H34z"/>`,
    swirl: `<path d="M32 14c-10 0-18 8-18 18 0-6 6-10 12-10M32 50c10 0 18-8 18-18 0 6-6 10-12 10" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round"/><circle cx="32" cy="32" r="6"/>`,
    waves: `<path d="M12 26c5-5 10 5 15 0s10 5 15 0 7 3 10 2M12 36c5-5 10 5 15 0s10 5 15 0 7 3 10 2M12 46c5-5 10 5 15 0s10 5 15 0 7 3 10 2" fill="none" stroke="#fff" stroke-width="3.6" stroke-linecap="round"/>`,
    haze: `<path d="M14 24h26M14 32h36M14 40h22M44 40h6M20 48h22" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round"/>`,
    hospital: `<rect x="17" y="17" width="30" height="30" rx="4"/><path d="M29 22h6v7h7v6h-7v7h-6v-7h-7v-6h7z" fill="C"/>`,
    station: `<path d="M14 30 32 15l18 15v19H14z"/><path d="M25 49V37h14v12z" fill="C"/><path d="M30 39h4M30 43h4" stroke="#fff" stroke-width="1.6"/>`,
    aed: `<path d="M32 50S14 39 14 26c0-7 5-11 10-11 4 0 6.5 2.5 8 5 1.5-2.5 4-5 8-5 5 0 10 4 10 11 0 13-18 24-18 24z"/><path d="M34 20 27 32h6l-3 11 9-14h-6l3-9z" fill="C"/>`,
  };
  const ICONS = {
    "d-medical": ["ambulance", "--medical"], "d-traffic": ["car", "--traffic"], "d-fire": ["flame", "--fire"],
    "d-rescue": ["ring", "--rescue"], "d-other": ["alert", "--other"],
    heli: ["heli", "--air"], plane: ["plane", "--emerg"], football: ["football", "--sideline"], basketball: ["basketball", "--sideline"],
    "g-live": ["stadium", "--live"], "g-upcoming": ["stadium", "--game"], at: ["cross", "--sideline"],
    "h-wildfire": ["flame", "--wildfire"], "h-earthquake": ["quake", "--quake"], "h-storm": ["bolt", "--storm"],
    "h-storm-injury": ["bolt", "--fire"], "h-hurricane": ["swirl", "--hurricane"], "h-flood": ["waves", "--flood"], "h-air": ["haze", "--airq"],
    hospital: ["hospital", "--hospital"], alert: ["bolt", "--fire"],
    "p-fire": ["station", "--fire"], "p-ems": ["station", "--medical"], "p-aed": ["aed", "--ok"],
  };
  function iconSvg(name) {
    const [glyph, colorVar] = ICONS[name], color = css(colorVar);
    return `<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><circle cx="32" cy="32" r="29" fill="${color}" stroke="#0a1119" stroke-width="3"/><circle cx="32" cy="32" r="29" fill="none" stroke="#fff" stroke-opacity=".85" stroke-width="2"/><g fill="#fff">${GLYPH[glyph].replaceAll('"C"', `"${color}"`)}</g></svg>`;
  }
  const iconUrl = name => "data:image/svg+xml;charset=utf-8," + encodeURIComponent(iconSvg(name));

  // ---------- data ----------
  async function getJson(name) {
    const res = await fetch(url(name), { cache: "no-store" });
    if (!res.ok) throw new Error(res.status);
    return res.json();
  }
  const empty = { type: "FeatureCollection", features: [] };
  function totals(d) {
    const teams = (d.sideline && d.sideline.teams) || [];
    return {
      calls: d.dispatch.features.reduce((a, f) => a + f.properties.n, 0),
      air: d.aircraft.features.length,
      emergencies: (d.emergency_aircraft || empty).features.length,
      athletes: teams.reduce((a, t) => a + t.players.length, 0),
      out: teams.reduce((a, t) => a + t.players.filter(p => p.status === "Out").length, 0),
      gamesLive: (d.games || empty).features.filter(f => f.properties.state === "live").length,
      games: (d.games || empty).features.length,
      hazards: (d.hazards || empty).features.length,
      alerts: d.alerts.features.length,
      sourcesUp: d.sources.filter(s => s.ok).length, sources: d.sources.length,
      cities: new Set(d.sources.filter(s => s.kind === "dispatch" && s.ok).map(s => s.area)).size,
    };
  }

  // "Happening now": the most notable things in the latest data.
  function feedItems(d) {
    const items = [];
    for (const f of (d.emergency_aircraft || empty).features) {
      const p = f.properties;
      items.push({ icon: "plane", live: true, text: `Aircraft emergency${p.callsign ? " · " + p.callsign : ""}`, sub: [p.model, p.origin && "from " + p.origin].filter(Boolean).join(" · "), at: f.geometry.coordinates, zoom: 7 });
    }
    for (const f of (d.games || empty).features) {
      const p = f.properties;
      items.push({ icon: "g-" + p.state, live: p.state === "live", text: p.title, sub: p.state === "live" ? `${p.league} · athletic trainers on the sideline` : `${p.league} · ${p.start}`, at: f.geometry.coordinates, zoom: 13 });
    }
    for (const f of (d.hazards || empty).features) {
      const p = f.properties;
      if (p.kind === "hurricane" || p.kind === "storm-injury") items.push({ icon: "h-" + p.kind, live: true, text: p.title, sub: p.detail, at: f.geometry.coordinates, zoom: 6 });
    }
    const busiest = d.dispatch.features.filter(f => f.properties.place).sort((a, b) => b.properties.n - a.properties.n).slice(0, 3);
    for (const f of busiest) {
      const p = f.properties;
      items.push({ icon: "d-" + p.top, live: true, text: `${p.n} active 911 calls`, sub: p.place, at: f.geometry.coordinates, zoom: 10 });
    }
    return items.sort((a, b) => Number(b.live) - Number(a.live));
  }
  function renderFeed(ul, items, onPick, max = 8) {
    if (!items.length) { ul.innerHTML = `<li class="empty">Nothing notable right now.</li>`; return; }
    ul.innerHTML = items.slice(0, max).map((it, i) => `<li><${onPick ? "button type=\"button\"" : `a href="map.html?at=${it.at[0].toFixed(3)},${it.at[1].toFixed(3)},${it.zoom}"`} data-i="${i}">
      <img src="${iconUrl(it.icon)}" alt=""><span class="t">${esc(it.text)}<span>${esc(it.sub)}</span></span>
      <span class="tag ${it.live ? "" : "soft"}">${it.live ? "Live" : "Today"}</span></${onPick ? "button" : "a"}></li>`).join("");
    if (onPick) ul.querySelectorAll("button").forEach(b => b.addEventListener("click", () => onPick(items[Number(b.dataset.i)])));
  }

  // ---------- page chrome ----------
  const PAGES = [["index.html", "Home"], ["map.html", "Live map"], ["sideline.html", "Sideline"], ["trends.html", "Trends"], ["recap.html", "Daily recap"], ["about.html", "About"]];
  function chrome(current) {
    const nav = document.createElement("header");
    nav.className = "nav";
    nav.innerHTML = `<div class="wrap">
      <a class="logo" href="index.html" aria-label="On Scene home"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="none" stroke="#f2a93b" stroke-width="2"/><circle cx="12" cy="12" r="4" fill="#f2a93b"/></svg>On <span>Scene</span></a>
      <nav class="links" aria-label="Main">${PAGES.map(([href, label]) => `<a href="${href}"${href === current ? ' aria-current="page"' : ""}>${label}</a>`).join("")}</nav>
      <div class="navstatus"><span class="livedot stale" id="navdot"></span><span class="txt" id="navtime">Connecting…</span></div>
      <button class="menu-btn" type="button" aria-label="Menu" aria-expanded="false"><svg viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></button>
    </div>`;
    document.body.prepend(nav);
    const btn = nav.querySelector(".menu-btn");
    btn.addEventListener("click", () => { const open = nav.classList.toggle("open"); btn.setAttribute("aria-expanded", String(open)); });
  }
  function footer() {
    const f = document.createElement("footer");
    f.className = "foot";
    f.innerHTML = `<div class="wrap"><span><b>On Scene</b> · a live view of emergency response, built only from public data.</span>
      <span><b>Not an emergency service.</b> In an emergency, call 911.</span><span><a href="about.html">Sources & privacy</a></span></div>`;
    document.body.append(f);
  }
  function setStatus(generated) {
    const mins = (Date.now() - parseGen(generated)) / 60000;
    const dot = document.getElementById("navdot"), t = document.getElementById("navtime");
    if (dot) dot.classList.toggle("stale", mins > 20);
    if (t) t.textContent = `Live · updated ${ago(generated)}`;
  }

  // Count a number up to its value (respects reduced motion).
  function countTo(el, value, ms = 1100) {
    if (!el) return;
    const from = Number(el.dataset.v || 0);
    el.dataset.v = value;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches || from === value) { el.textContent = value.toLocaleString(); return; }
    const t0 = performance.now();
    const step = t => {
      const k = Math.min(1, (t - t0) / ms), e = 1 - Math.pow(1 - k, 3);
      el.textContent = Math.round(from + (value - from) * e).toLocaleString();
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  window.OS = { url, css, esc, ago, parseGen, iconUrl, ICONS, getJson, totals, chrome, footer, setStatus, countTo, empty, LOCAL, feedItems, renderFeed };
})();
