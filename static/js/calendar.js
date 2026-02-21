/* calendar.js — populates the calendar grid and handles filters */
(function () {
  "use strict";

  const events = window.EVENTS || [];

  // ── Assign a stable colour index per venue key ──
  const venueKeys = [...new Set(events.map(e => e.venue_key))].sort();
  const venueColor = {};
  venueKeys.forEach((k, i) => { venueColor[k] = i % 6; });

  // ── Render all event chips into the correct day cells ──
  function renderChip(event) {
    const container = document.querySelector(`.cal-events[data-date="${event.date}"]`);
    if (!container) return;

    const a = document.createElement("a");
    a.href = event.url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.className = "event-chip venue-color-" + (venueColor[event.venue_key] ?? 0);
    if (event.sold_out) a.classList.add("sold-out");

    // Encode filter-relevant data as attributes for fast filtering
    a.dataset.venue = event.venue_key;
    a.dataset.timeofday = event.time_of_day;
    a.dataset.soldOut = event.sold_out ? "1" : "0";

    const title = document.createElement("span");
    title.textContent = event.title;
    a.appendChild(title);

    if (event.time) {
      const t = document.createElement("span");
      t.className = "chip-time";
      t.textContent = formatTime(event.time) + (event.venue_name ? " · " + event.venue_name : "");
      a.appendChild(t);
    } else if (event.venue_name) {
      const t = document.createElement("span");
      t.className = "chip-time";
      t.textContent = event.venue_name;
      a.appendChild(t);
    }

    container.appendChild(a);
  }

  function formatTime(str) {
    // str is "HH:MM"; convert to "7:30 pm" style
    const [h, m] = str.split(":").map(Number);
    const suffix = h >= 12 ? "pm" : "am";
    const h12 = h % 12 || 12;
    return m === 0 ? `${h12} ${suffix}` : `${h12}:${String(m).padStart(2, "0")} ${suffix}`;
  }

  events.forEach(renderChip);

  // ── Filters ──
  function getCheckedValues(name) {
    return [...document.querySelectorAll(`input[name="${name}"]:checked`)].map(el => el.value);
  }

  function applyFilters() {
    const activeVenues = new Set(getCheckedValues("venue"));
    const activeTimes = new Set(getCheckedValues("timeofday"));
    const hideSoldOut = document.getElementById("hideSoldOut").checked;

    const chips = document.querySelectorAll(".event-chip");
    chips.forEach(chip => {
      const visible =
        activeVenues.has(chip.dataset.venue) &&
        activeTimes.has(chip.dataset.timeofday) &&
        !(hideSoldOut && chip.dataset.soldOut === "1");
      chip.style.display = visible ? "" : "none";
    });

    // Hide months where every day has no visible chips
    let totalVisible = 0;
    document.querySelectorAll(".month").forEach(month => {
      const anyVisible = [...month.querySelectorAll(".event-chip")].some(c => c.style.display !== "none");
      month.toggleAttribute("data-hidden", !anyVisible);
      if (anyVisible) totalVisible++;
    });

    const emptyMsg = document.getElementById("empty-msg");
    if (emptyMsg) emptyMsg.style.display = totalVisible === 0 ? "" : "none";
  }

  // Attach listeners
  document.querySelectorAll(".filters input").forEach(input => {
    input.addEventListener("change", applyFilters);
  });

  // Initial render (everything visible by default)
  applyFilters();
})();
