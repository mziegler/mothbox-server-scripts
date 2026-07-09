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

// Magnifier zoom, in the style of a product-image hover-zoom: cursor (or
// touch) position over the image directly selects which region is shown at
// a fixed magnification, via CSS transform-origin -- no click-drag needed.
const MIN_MAGNIFICATION = 2;
const MAX_MAGNIFICATION = 4;

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function initLightbox() {
  const lightbox = document.getElementById("lightbox");
  const wrap = lightbox.querySelector(".lightbox-image-wrap");
  const lightboxImg = wrap.querySelector("img");
  const closeBtn = lightbox.querySelector(".lightbox-close");
  let magnification = MIN_MAGNIFICATION;

  function sizeWrapToFit() {
    // Mirrors object-fit: contain's own math, but on a fixed-size wrapper
    // (rather than the img's auto-sized box) so the magnifier's zoomed
    // content stays clipped to the original photo's on-screen footprint.
    const naturalW = lightboxImg.naturalWidth || 1;
    const naturalH = lightboxImg.naturalHeight || 1;
    const maxW = window.innerWidth * 0.9;
    const maxH = window.innerHeight * 0.8;
    const ratio = Math.min(maxW / naturalW, maxH / naturalH, 1);
    wrap.style.width = `${naturalW * ratio}px`;
    wrap.style.height = `${naturalH * ratio}px`;
    magnification = clamp(1 / ratio, MIN_MAGNIFICATION, MAX_MAGNIFICATION);
  }

  function updateMagnifierOrigin(clientX, clientY) {
    const rect = wrap.getBoundingClientRect();
    const nx = clamp((clientX - rect.left) / rect.width, 0, 1);
    const ny = clamp((clientY - rect.top) / rect.height, 0, 1);
    lightboxImg.style.transformOrigin = `${nx * 100}% ${ny * 100}%`;
  }

  function startMagnifying(clientX, clientY) {
    updateMagnifierOrigin(clientX, clientY);
    lightboxImg.style.transform = `scale(${magnification})`;
    lightboxImg.classList.add("magnifying");
  }

  function stopMagnifying() {
    lightboxImg.style.transform = "scale(1)";
    lightboxImg.classList.remove("magnifying");
  }

  // Touch devices get the whole screen to zoom in, rather than the smaller
  // fit-sized box mouse users see -- entered/exited around each touch
  // gesture so the page layout is otherwise untouched.
  function enterFullscreenZoom() {
    wrap.classList.add("fullscreen-zoom");
    wrap.style.width = "";
    wrap.style.height = "";
  }

  function exitFullscreenZoom() {
    wrap.classList.remove("fullscreen-zoom");
    sizeWrapToFit();
  }

  function openLightbox(src, alt) {
    lightbox.classList.remove("hidden");
    lightboxImg.alt = alt;
    stopMagnifying();
    const onLoad = () => {
      lightboxImg.removeEventListener("load", onLoad);
      sizeWrapToFit();
    };
    lightboxImg.addEventListener("load", onLoad);
    lightboxImg.src = src;
  }

  function close() {
    lightbox.classList.add("hidden");
    stopMagnifying();
    wrap.classList.remove("fullscreen-zoom");
    lightboxImg.src = "";
  }

  document.getElementById("devices").addEventListener("click", (e) => {
    if (e.target.tagName === "IMG") {
      openLightbox(e.target.src, e.target.alt);
    }
  });

  wrap.addEventListener("mousemove", (e) => {
    startMagnifying(e.clientX, e.clientY);
  });
  wrap.addEventListener("mouseleave", stopMagnifying);

  // Touch has no hover, so a finger held on the image drives the same
  // cursor-position-based magnifier, updating as it moves.
  wrap.addEventListener(
    "touchstart",
    (e) => {
      const t = e.touches[0];
      if (t) {
        enterFullscreenZoom();
        startMagnifying(t.clientX, t.clientY);
      }
      e.preventDefault();
    },
    { passive: false }
  );
  wrap.addEventListener(
    "touchmove",
    (e) => {
      const t = e.touches[0];
      if (t) updateMagnifierOrigin(t.clientX, t.clientY);
      e.preventDefault();
    },
    { passive: false }
  );
  function endTouchZoom() {
    stopMagnifying();
    exitFullscreenZoom();
  }
  wrap.addEventListener("touchend", endTouchZoom);
  wrap.addEventListener("touchcancel", endTouchZoom);

  window.addEventListener("resize", () => {
    // Skip while a touch zoom has the wrap pinned fullscreen (e.g. an
    // orientation change mid-touch) -- its CSS is already viewport-relative,
    // and sizeWrapToFit() would otherwise overwrite it with fit-sized
    // inline styles that outrank that class.
    if (!lightbox.classList.contains("hidden") && !wrap.classList.contains("fullscreen-zoom")) {
      stopMagnifying();
      sizeWrapToFit();
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
