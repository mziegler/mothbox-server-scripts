// Renders the Mothbox livestream dashboard from data/mothboxes.json (written
// by livestream.py). This file is fully static and never generated -- all
// dynamic content comes from that one JSON fetch.

const DATA_URL = "data/mothboxes.json";
// Keep in sync with LIVESTREAM_REFRESH_SECONDS in mothboxServerConfig.py.
const DEFAULT_REFRESH_MS = 20000;
const TICK_INTERVAL_MS = 20000;

const STATUS_META = {
  "ok": { label: "Online", className: "status-ok" },
  "starting-up": { label: "Starting up…", className: "status-starting-up" },
  "possible-outage": { label: "⚠ Mothbox offline (probably a power outage)", className: "status-possible-outage" },
  "expected-off": { label: "Off (per schedule)", className: "status-expected-off" },
  "no-photo-yet": { label: "No photo received yet", className: "status-no-photo-yet" },
};

async function fetchMothboxData() {
  const res = await fetch(DATA_URL, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} fetching ${DATA_URL}`);
  }
  return res.json();
}

function pluralize(value, unit) {
  return `${value} ${unit}${value === 1 ? "" : "s"}`;
}

// Handles both directions: a past isoString reads "N minutes ago", a future
// one (e.g. the next scheduled on-time) reads "in N minutes".
function formatRelativeTime(isoString, now) {
  if (!isoString) return "never";
  const then = new Date(isoString);
  const diffMin = Math.round((now - then) / 60000);
  const future = diffMin < 0;
  const absMin = Math.abs(diffMin);

  if (absMin < 1) return "just now";
  if (absMin < 60) return future ? `in ${pluralize(absMin, "minute")}` : `${pluralize(absMin, "minute")} ago`;
  const absHr = Math.round(absMin / 60);
  if (absHr < 24) return future ? `in ${pluralize(absHr, "hour")}` : `${pluralize(absHr, "hour")} ago`;
  const absDay = Math.round(absHr / 24);
  return future ? `in ${pluralize(absDay, "day")}` : `${pluralize(absDay, "day")} ago`;
}

function formatAbsoluteTime(isoString, timeZone) {
  if (!isoString) return "";
  const d = new Date(isoString);
  const options = {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    // Appends the zone's own abbreviation/offset (e.g. "GMT-5") so the two
    // times below are self-explanatory without hardcoding a region name --
    // MOTHBOX_ON_HOURS (and so the Mothbox's timezone) is configurable per
    // deployment, and the viewer's own timezone is obviously unknown ahead
    // of time.
    timeZoneName: "short",
  };
  if (timeZone) options.timeZone = timeZone;
  // Omitting timeZone makes toLocaleString use the browser's own local zone.
  return d.toLocaleString(undefined, options);
}

function buildMothboxTimeText(isoString, timeZone, now) {
  return `Latest photo: ${formatAbsoluteTime(isoString, timeZone)} (${formatRelativeTime(isoString, now)})`;
}

function buildNextOnText(isoString, timeZone, now) {
  return `Next scheduled on: ${formatAbsoluteTime(isoString, timeZone)} (${formatRelativeTime(isoString, now)})`;
}

function buildDeviceCard(device, mothboxTimeZone, nextOnTime) {
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
    timestamp.dataset.tz = mothboxTimeZone || "";
    timestamp.textContent = buildMothboxTimeText(device.latestPhotoTimestamp, mothboxTimeZone, new Date());
  } else {
    timestamp.textContent = "Latest photo: none yet";
  }
  card.appendChild(timestamp);

  if (device.latestPhotoTimestamp) {
    const localTime = document.createElement("p");
    localTime.className = "timestamp timestamp-local";
    localTime.textContent = `Your time: ${formatAbsoluteTime(device.latestPhotoTimestamp)}`;
    card.appendChild(localTime);
  }

  if (device.status === "expected-off" && nextOnTime) {
    const nextOn = document.createElement("p");
    nextOn.className = "timestamp next-on-time";
    nextOn.dataset.nextOn = nextOnTime;
    nextOn.dataset.tz = mothboxTimeZone || "";
    nextOn.textContent = buildNextOnText(nextOnTime, mothboxTimeZone, new Date());
    card.appendChild(nextOn);
  }

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

  const mothboxTimeZone = data.schedule && data.schedule.timezone;
  const nextOnTime = data.schedule && data.schedule.nextOnTime;
  data.devices.forEach((device) => container.appendChild(buildDeviceCard(device, mothboxTimeZone, nextOnTime)));
}

function tickRelativeTimes() {
  const now = new Date();
  document.querySelectorAll(".timestamp[data-timestamp]").forEach((el) => {
    const iso = el.dataset.timestamp;
    if (!iso) return;
    el.textContent = buildMothboxTimeText(iso, el.dataset.tz, now);
  });
  document.querySelectorAll(".timestamp[data-next-on]").forEach((el) => {
    const iso = el.dataset.nextOn;
    if (!iso) return;
    el.textContent = buildNextOnText(iso, el.dataset.tz, now);
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
    renderDevices(data);
    setStatusBanner(null);
  } catch (err) {
    setStatusBanner("Could not reach the livestream data -- showing the last known state.");
  }
}

// Mouse: a product-image-style hover magnifier -- cursor position over the
// image directly selects which region is shown, at a fixed magnification,
// via CSS transform-origin. Touch gets a different interaction instead (see
// initLightbox below): pinch-to-zoom plus drag-to-pan, since there's no
// hover to drive a magnifier from.
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

  // Pinch-to-zoom + drag-to-pan for touch, as an alternative to the mouse
  // hover magnifier above -- two fingers pinch to set an arbitrary zoom
  // level (anchored at the pinch midpoint so that point stays under the
  // fingers), and once zoomed, one finger drags to pan. Unlike the hover
  // magnifier, the zoom level persists after fingers lift, so users can let
  // go and still look at the detail; double-tap zooms to a fixed level, or
  // back out to fit if already zoomed.
  const TOUCH_MIN_SCALE = 1;
  const TOUCH_MAX_SCALE = 8;
  const DOUBLE_TAP_SCALE = 3;
  const DOUBLE_TAP_MS = 300;
  const DOUBLE_TAP_MOVE_PX = 40;
  const TAP_MOVE_PX = 10;

  let touchScale = 1;
  let touchX = 0;
  let touchY = 0;
  let pinchStart = null; // {dist, scale}
  let panStart = null; // {x, y, baseX, baseY}
  let singleTouchStart = null; // {x, y}
  let gestureHadMultiTouch = false;
  let lastTapTime = 0;
  let lastTapPos = { x: 0, y: 0 };

  function touchDistance(a, b) {
    return Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
  }

  function touchMidpoint(a, b) {
    return { x: (a.clientX + b.clientX) / 2, y: (a.clientY + b.clientY) / 2 };
  }

  function applyTouchTransform() {
    lightboxImg.style.transformOrigin = "center center";
    lightboxImg.style.transform = `translate(${touchX}px, ${touchY}px) scale(${touchScale})`;
    lightboxImg.classList.toggle("magnifying", touchScale > 1.01);
  }

  function clampTouchPan() {
    // Standard "don't pan past the edges" clamp: once the scaled image is
    // smaller than the viewport in a dimension, there's nothing to pan
    // there, so it's forced back to centered (0) in that dimension.
    const rect = wrap.getBoundingClientRect();
    const maxX = Math.max(0, (rect.width * touchScale - rect.width) / 2);
    const maxY = Math.max(0, (rect.height * touchScale - rect.height) / 2);
    touchX = clamp(touchX, -maxX, maxX);
    touchY = clamp(touchY, -maxY, maxY);
  }

  function setTouchZoom(newScale, anchorX, anchorY) {
    // wrap itself never transforms, so its rect is a stable reference for
    // converting the anchor point into the image's own (scale-independent)
    // local coordinates, then back out at the new scale -- keeping that
    // point fixed under the fingers/tap as the scale changes.
    const rect = wrap.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    const curCenterX = centerX + touchX;
    const curCenterY = centerY + touchY;
    const localX = (anchorX - curCenterX) / touchScale;
    const localY = (anchorY - curCenterY) / touchScale;
    touchScale = clamp(newScale, TOUCH_MIN_SCALE, TOUCH_MAX_SCALE);
    touchX = anchorX - centerX - touchScale * localX;
    touchY = anchorY - centerY - touchScale * localY;
    clampTouchPan();
    applyTouchTransform();
  }

  function resetTouchZoom() {
    touchScale = 1;
    touchX = 0;
    touchY = 0;
    applyTouchTransform();
    exitFullscreenZoom();
  }

  function handlePossibleDoubleTap(touch) {
    const now = Date.now();
    const moved = Math.hypot(touch.clientX - lastTapPos.x, touch.clientY - lastTapPos.y);
    const isDouble = now - lastTapTime < DOUBLE_TAP_MS && moved < DOUBLE_TAP_MOVE_PX;
    lastTapTime = isDouble ? 0 : now; // consumed, so a triple-tap doesn't immediately re-trigger
    lastTapPos = { x: touch.clientX, y: touch.clientY };
    if (!isDouble) return;
    if (touchScale > 1.01) {
      resetTouchZoom();
    } else {
      enterFullscreenZoom();
      setTouchZoom(DOUBLE_TAP_SCALE, touch.clientX, touch.clientY);
    }
  }

  function openLightbox(src, alt) {
    lightbox.classList.remove("hidden");
    lightboxImg.alt = alt;
    stopMagnifying();
    touchScale = 1;
    touchX = 0;
    touchY = 0;
    applyTouchTransform();
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
    touchScale = 1;
    touchX = 0;
    touchY = 0;
    applyTouchTransform();
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

  wrap.addEventListener(
    "touchstart",
    (e) => {
      if (e.touches.length === 2) {
        enterFullscreenZoom();
        pinchStart = { dist: touchDistance(e.touches[0], e.touches[1]), scale: touchScale };
        panStart = null;
        gestureHadMultiTouch = true;
      } else if (e.touches.length === 1) {
        gestureHadMultiTouch = false;
        singleTouchStart = { x: e.touches[0].clientX, y: e.touches[0].clientY };
        pinchStart = null;
        panStart =
          touchScale > 1.01
            ? { x: e.touches[0].clientX, y: e.touches[0].clientY, baseX: touchX, baseY: touchY }
            : null;
      }
      e.preventDefault();
    },
    { passive: false }
  );

  wrap.addEventListener(
    "touchmove",
    (e) => {
      if (e.touches.length === 2 && pinchStart) {
        gestureHadMultiTouch = true;
        const dist = touchDistance(e.touches[0], e.touches[1]);
        const mid = touchMidpoint(e.touches[0], e.touches[1]);
        setTouchZoom(pinchStart.scale * (dist / pinchStart.dist), mid.x, mid.y);
      } else if (e.touches.length === 1 && panStart) {
        touchX = panStart.baseX + (e.touches[0].clientX - panStart.x);
        touchY = panStart.baseY + (e.touches[0].clientY - panStart.y);
        clampTouchPan();
        applyTouchTransform();
      }
      e.preventDefault();
    },
    { passive: false }
  );

  function handleTouchEnd(e) {
    if (e.touches.length === 1) {
      // Dropped from two fingers to one -- restart the pan baseline from
      // here so the image doesn't jump.
      pinchStart = null;
      panStart =
        touchScale > 1.01
          ? { x: e.touches[0].clientX, y: e.touches[0].clientY, baseX: touchX, baseY: touchY }
          : null;
      return;
    }
    if (e.touches.length === 0) {
      const endedTouch = e.changedTouches[0];
      if (!gestureHadMultiTouch && singleTouchStart && endedTouch) {
        const moved = Math.hypot(
          endedTouch.clientX - singleTouchStart.x,
          endedTouch.clientY - singleTouchStart.y
        );
        if (moved < TAP_MOVE_PX) handlePossibleDoubleTap(endedTouch);
      }
      pinchStart = null;
      panStart = null;
      singleTouchStart = null;
      // A pinch-out back to (or below) fit snaps fully back; otherwise the
      // zoom persists after the fingers lift so the user can look at it.
      if (touchScale <= 1.01) resetTouchZoom();
    }
  }
  wrap.addEventListener("touchend", handleTouchEnd);
  wrap.addEventListener("touchcancel", handleTouchEnd);

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
