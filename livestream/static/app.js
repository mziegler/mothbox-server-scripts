// Renders the Mothbox livestream dashboard from data/mothboxes.json (written
// by livestream.py). This file is fully static and never generated -- all
// dynamic content comes from that one JSON fetch.

const DATA_URL = "data/mothboxes.json";
// Keep in sync with LIVESTREAM_REFRESH_SECONDS in mothboxServerConfig.py.
const DEFAULT_REFRESH_MS = 20000;
const TICK_INTERVAL_MS = 20000;

const STATUS_META = {
  "ok": { label: "Online", className: "status-ok" },
  "possible-outage": { label: "⚠ Possible power outage or technical problem", className: "status-possible-outage" },
  "expected-off": { label: "Off (per schedule)", className: "status-expected-off" },
  "no-photo-yet": { label: "No photo received yet", className: "status-no-photo-yet" },
};

let scheduleRendered = false;

async function fetchMothboxData() {
  const res = await fetch(DATA_URL, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} fetching ${DATA_URL}`);
  }
  return res.json();
}

function formatHourLabel(hour) {
  const h12 = hour % 12 === 0 ? 12 : hour % 12;
  const suffix = hour < 12 ? "am" : "pm";
  return `${h12}${suffix}`;
}

function formatHourRanges(onHours) {
  if (!onHours || !onHours.length) {
    return "no scheduled on-hours configured";
  }
  const sorted = [...onHours].sort((a, b) => a - b);
  const ranges = [];
  let start = sorted[0];
  let prev = sorted[0];
  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i] === prev + 1) {
      prev = sorted[i];
      continue;
    }
    ranges.push([start, prev]);
    start = sorted[i];
    prev = sorted[i];
  }
  ranges.push([start, prev]);
  return ranges
    .map(([s, e]) => `${formatHourLabel(s)}–${formatHourLabel((e + 1) % 24)}`)
    .join(", ");
}

function renderScheduleExplanation(schedule) {
  const el = document.getElementById("schedule-explanation");
  if (!el || !schedule) return;
  const ranges = formatHourRanges(schedule.onHours);
  el.textContent =
    `Mothboxes are scheduled to power on during: ${ranges} (${schedule.timezone} local time). ` +
    `Outside those windows, an "off" status is expected and not a problem -- ` +
    `only a stale photo while a device is expected to be on may indicate a power ` +
    `outage or technical issue.`;
}

function formatRelativeTime(isoString, now) {
  if (!isoString) return "never";
  const then = new Date(isoString);
  const diffMin = Math.round((now - then) / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin === 1) return "1 minute ago";
  if (diffMin < 60) return `${diffMin} minutes ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr === 1) return "1 hour ago";
  if (diffHr < 24) return `${diffHr} hours ago`;
  const diffDay = Math.round(diffHr / 24);
  return diffDay === 1 ? "1 day ago" : `${diffDay} days ago`;
}

function formatAbsoluteTime(isoString) {
  if (!isoString) return "";
  const d = new Date(isoString);
  return d.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function buildDeviceCard(device) {
  const meta = STATUS_META[device.status] || { label: device.status, className: "" };

  const card = document.createElement("div");
  card.className = `device-card ${meta.className}`;

  const heading = document.createElement("h2");
  heading.textContent = device.friendlyName;
  card.appendChild(heading);

  if (device.imageUrl) {
    const img = document.createElement("img");
    img.src = device.imageUrl;
    img.alt = device.friendlyName;
    img.loading = "lazy";
    card.appendChild(img);
  } else {
    const placeholder = document.createElement("div");
    placeholder.className = "no-image";
    placeholder.textContent = "No photo yet";
    card.appendChild(placeholder);
  }

  const badge = document.createElement("span");
  badge.className = `badge ${meta.className}`;
  badge.textContent = meta.label;
  card.appendChild(badge);

  const timestamp = document.createElement("p");
  timestamp.className = "timestamp";
  if (device.latestPhotoTimestamp) {
    timestamp.dataset.timestamp = device.latestPhotoTimestamp;
    timestamp.textContent =
      `Latest photo: ${formatAbsoluteTime(device.latestPhotoTimestamp)} ` +
      `(${formatRelativeTime(device.latestPhotoTimestamp, new Date())})`;
  } else {
    timestamp.textContent = "Latest photo: none yet";
  }
  card.appendChild(timestamp);

  if (device.description) {
    const desc = document.createElement("p");
    desc.className = "description";
    desc.textContent = device.description;
    card.appendChild(desc);
  }

  return card;
}

function renderDevices(data) {
  const container = document.getElementById("devices");
  container.innerHTML = "";

  if (!data.enabled) {
    const msg = document.createElement("p");
    msg.className = "disabled-message";
    msg.textContent = "The livestream is currently disabled.";
    container.appendChild(msg);
    return;
  }

  if (!data.devices || !data.devices.length) {
    const msg = document.createElement("p");
    msg.textContent = "No Mothbox devices configured.";
    container.appendChild(msg);
    return;
  }

  data.devices.forEach((device) => container.appendChild(buildDeviceCard(device)));
}

function tickRelativeTimes() {
  const now = new Date();
  document.querySelectorAll(".timestamp[data-timestamp]").forEach((el) => {
    const iso = el.dataset.timestamp;
    if (!iso) return;
    el.textContent = `Latest photo: ${formatAbsoluteTime(iso)} (${formatRelativeTime(iso, now)})`;
  });
}

function setStatusBanner(message) {
  const el = document.getElementById("status-banner");
  if (!el) return;
  if (message) {
    el.textContent = message;
    el.classList.remove("hidden");
  } else {
    el.classList.add("hidden");
  }
}

async function refreshLoop() {
  try {
    const data = await fetchMothboxData();
    if (!scheduleRendered && data.schedule) {
      renderScheduleExplanation(data.schedule);
      scheduleRendered = true;
    }
    renderDevices(data);
    setStatusBanner(null);
  } catch (err) {
    setStatusBanner("Could not reach the livestream data -- showing the last known state.");
  }
}

function initLightbox() {
  const lightbox = document.getElementById("lightbox");
  const lightboxImg = lightbox.querySelector("img");
  const closeBtn = lightbox.querySelector(".lightbox-close");

  function close() {
    lightbox.classList.add("hidden");
    lightboxImg.src = "";
  }

  document.getElementById("devices").addEventListener("click", (e) => {
    if (e.target.tagName === "IMG") {
      lightboxImg.src = e.target.src;
      lightboxImg.alt = e.target.alt;
      lightbox.classList.remove("hidden");
    }
  });

  closeBtn.addEventListener("click", close);
  lightbox.addEventListener("click", (e) => {
    if (e.target === lightbox) close();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") close();
  });
}

function init() {
  initLightbox();
  refreshLoop();
  setInterval(tickRelativeTimes, TICK_INTERVAL_MS);
  setInterval(refreshLoop, DEFAULT_REFRESH_MS);
}

init();
