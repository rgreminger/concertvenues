/* calendar.js — populates the calendar grid + agenda list and handles filters */
(function () {
  "use strict";

  const events = window.EVENTS || [];
  const today = window.TODAY || "";

  // ── Assign a stable colour index per venue key ──
  const venueKeys = [...new Set(events.map(e => e.venue_key))].sort();
  const venueColor = {};
  venueKeys.forEach((k, i) => { venueColor[k] = i % 6; });

  function formatTime(str) {
    const [h, m] = str.split(":").map(Number);
    const suffix = h >= 12 ? "pm" : "am";
    const h12 = h % 12 || 12;
    return m === 0 ? `${h12} ${suffix}` : `${h12}:${String(m).padStart(2, "0")} ${suffix}`;
  }

  // ── Calendar grid chips ──
  function renderChip(event) {
    const container = document.querySelector(`.cal-events[data-date="${event.date}"]`);
    if (!container) return;

    const a = document.createElement("a");
    a.href = event.url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.className = "event-chip venue-color-" + (venueColor[event.venue_key] ?? 0);
    if (event.sold_out) a.classList.add("sold-out");
    a.dataset.venue = event.venue_key;
    a.dataset.timeofday = event.time_of_day;
    a.dataset.soldOut = event.sold_out ? "1" : "0";

    const title = document.createElement("span");
    title.textContent = event.title;
    a.appendChild(title);

    const meta = event.time
      ? formatTime(event.time) + (event.venue_name ? " · " + event.venue_name : "")
      : event.venue_name || "";
    if (meta) {
      const t = document.createElement("span");
      t.className = "chip-time";
      t.textContent = meta;
      a.appendChild(t);
    }

    container.appendChild(a);
  }

  // ── Agenda list ──
  function buildAgenda() {
    const container = document.getElementById("agenda");
    if (!container) return;

    // Group events by date
    const byDate = {};
    events.forEach(e => {
      if (!byDate[e.date]) byDate[e.date] = [];
      byDate[e.date].push(e);
    });

    const dates = Object.keys(byDate).sort();
    dates.forEach(dateStr => {
      const row = document.createElement("div");
      row.className = "agenda-day";
      row.dataset.date = dateStr;
      if (dateStr === today) row.setAttribute("data-today", "");

      // Date column
      const [year, month, day] = dateStr.split("-");
      const d = new Date(Number(year), Number(month) - 1, Number(day));
      const dow = d.toLocaleDateString("en-GB", { weekday: "short" });
      const mon = d.toLocaleDateString("en-GB", { month: "short" });

      const dateCol = document.createElement("div");
      dateCol.className = "agenda-date";
      dateCol.innerHTML = `<span class="agenda-day-num">${Number(day)}</span>${dow}<br>${mon}`;
      row.appendChild(dateCol);

      // Events column
      const eventsCol = document.createElement("div");
      eventsCol.className = "agenda-events";
      eventsCol.dataset.date = dateStr;

      byDate[dateStr].forEach(event => {
        const a = document.createElement("a");
        a.href = event.url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        a.className = "agenda-chip venue-color-" + (venueColor[event.venue_key] ?? 0);
        if (event.sold_out) a.classList.add("sold-out");
        a.dataset.venue = event.venue_key;
        a.dataset.timeofday = event.time_of_day;
        a.dataset.soldOut = event.sold_out ? "1" : "0";

        const parts = [event.venue_name];
        if (event.time) parts.unshift(formatTime(event.time));
        if (event.price) parts.push(event.price);

        a.innerHTML = `${event.title}<span class="chip-meta">${parts.filter(Boolean).join(" · ")}</span>`;
        eventsCol.appendChild(a);
      });

      row.appendChild(eventsCol);
      container.appendChild(row);
    });
  }

  events.forEach(renderChip);
  buildAgenda();

  // ── Filters ──
  function getCheckedValues(name) {
    return [...document.querySelectorAll(`input[name="${name}"]:checked`)].map(el => el.value);
  }

  function applyFilters() {
    const activeVenues = new Set(getCheckedValues("venue"));
    const activeTimes = new Set(getCheckedValues("timeofday"));
    const hideSoldOut = document.getElementById("hideSoldOut").checked;

    function chipVisible(chip) {
      return activeVenues.has(chip.dataset.venue) &&
        activeTimes.has(chip.dataset.timeofday) &&
        !(hideSoldOut && chip.dataset.soldOut === "1");
    }

    // Calendar grid
    document.querySelectorAll(".event-chip").forEach(chip => {
      chip.style.display = chipVisible(chip) ? "" : "none";
    });

    // Agenda list
    document.querySelectorAll(".agenda-chip").forEach(chip => {
      chip.style.display = chipVisible(chip) ? "" : "none";
    });

    // Hide calendar months with no visible chips
    document.querySelectorAll(".month").forEach(month => {
      const anyVisible = [...month.querySelectorAll(".event-chip")].some(c => c.style.display !== "none");
      month.toggleAttribute("data-hidden", !anyVisible);
    });

    // Hide agenda rows with no visible chips
    document.querySelectorAll(".agenda-day").forEach(row => {
      const anyVisible = [...row.querySelectorAll(".agenda-chip")].some(c => c.style.display !== "none");
      row.style.display = anyVisible ? "" : "none";
    });

    const totalVisible = [...document.querySelectorAll(".event-chip")].some(c => c.style.display !== "none");
    const emptyMsg = document.getElementById("empty-msg");
    if (emptyMsg) emptyMsg.style.display = totalVisible ? "none" : "";
  }

  document.querySelectorAll(".filters input").forEach(input => {
    input.addEventListener("change", applyFilters);
  });

  applyFilters();
})();
