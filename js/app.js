(function () {
  var FEED_HTTPS = "https://sharvin0345.github.io/usd-news-calendar-/usd-news.ics";
  var toggle = document.querySelector("#show-medium");
  var status = document.querySelector("#status");
  var notice = document.querySelector("#notice");
  var counts = document.querySelector("#counts");
  var days = document.querySelector("#days");
  var updated = document.querySelector("#updated");
  var clock = document.querySelector("#clock");
  var calendarData = null;
  var didScroll = false;

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function showMedium() {
    return toggle.getAttribute("aria-pressed") === "true";
  }

  function setMedium(on) {
    toggle.setAttribute("aria-pressed", on ? "true" : "false");
    toggle.textContent = on ? "Showing medium impact" : "Show medium impact";
    try {
      localStorage.setItem("usd-news-show-medium", on ? "1" : "0");
    } catch (err) {
      /* private mode */
    }
    if (calendarData) render(calendarData);
  }

  function sessionBadge(labels) {
    if (labels.length === 1) return "Within 30 min of your " + labels[0] + " session";
    if (labels.length > 1) return "Within 30 min of your " + labels.join(" and ") + " sessions";
    return "";
  }

  function dayChip(dateKey, nowIso) {
    var today = GoldCalendar.dateKey(nowIso);
    if (dateKey === today) return "Today";
    if (dateKey === GoldCalendar.addDays(today, 1)) return "Tomorrow";
    var start = GoldCalendar.weekStartKey(nowIso);
    if (dateKey >= GoldCalendar.addDays(start, 7)) return "Next week";
    return "";
  }

  function render(data) {
    var nowIso = new Date().toISOString();
    var nowMs = Date.now();
    var events = (data.events || []).filter(function (event) {
      return GoldCalendar.inWindow(event.startsAt, nowIso);
    });
    var holidays = events.filter(function (event) { return event.impact === "Holiday"; });
    var mediumOn = showMedium();
    var visible = events.filter(function (event) {
      if (event.impact === "Holiday") return false;
      if (event.impact === "High") return true;
      return mediumOn && event.impact === "Medium";
    });

    var highAll = events.filter(function (event) { return event.impact === "High"; }).length;
    var highAhead = events.filter(function (event) {
      return event.impact === "High" && !GoldCalendar.isPast(event.startsAt, nowMs);
    }).length;
    var mediumAll = events.filter(function (event) { return event.impact === "Medium"; }).length;
    var countText = highAll + " high-impact";
    if (highAhead !== highAll) countText += " (" + highAhead + " still ahead)";
    countText += mediumOn
      ? ", " + mediumAll + " medium"
      : ". Medium is hidden (" + mediumAll + ")";
    counts.textContent = countText;

    notice.hidden = !data.notice;
    notice.textContent = data.notice || "";
    updated.textContent = data.generatedAt
      ? "List updated " + GoldCalendar.formatStamp(data.generatedAt) + "."
      : "";

    days.replaceChildren();
    if (holidays.length) {
      holidays.forEach(function (event) {
        days.appendChild(el(
          "p",
          "holiday-banner",
          GoldCalendar.formatDay(event.startsAt) + ". " + event.goldNote
        ));
      });
    }

    if (!visible.length) {
      status.hidden = false;
      status.textContent = mediumOn
        ? "No high or medium USD events in this week or next."
        : "No high-impact USD events in this week or next. Turn on medium impact to see the rest.";
      return;
    }
    status.hidden = true;

    var next = visible.find(function (event) {
      return !GoldCalendar.isPast(event.startsAt, nowMs);
    });
    var groups = [];
    var byKey = {};
    visible.forEach(function (event) {
      var key = GoldCalendar.dateKey(event.startsAt);
      if (!byKey[key]) {
        byKey[key] = [];
        groups.push(key);
      }
      byKey[key].push(event);
    });

    var nextNode = null;
    groups.forEach(function (key) {
      var sample = byKey[key][0].startsAt;
      var head = el("div", "day");
      head.appendChild(el("h2", null, GoldCalendar.formatDay(sample)));
      var chip = dayChip(key, nowIso);
      if (chip) head.appendChild(el("span", "day-chip", chip));
      days.appendChild(head);

      byKey[key].forEach(function (event) {
        var past = GoldCalendar.isPast(event.startsAt, nowMs);
        var near = GoldCalendar.nearSessionLabels(event.startsAt);
        var card = el("article", "card " + event.impact.toLowerCase());
        card.setAttribute("data-impact", event.impact);
        if (past) card.classList.add("past");
        if (near.length) card.classList.add("session");
        if (next && event.id === next.id) {
          card.classList.add("next-up");
          nextNode = card;
        }

        var top = el("div", "card-top");
        var time = el("p", "when", GoldCalendar.formatTime(event.startsAt));
        time.setAttribute("datetime", event.startsAt);
        top.appendChild(time);
        top.appendChild(el("span", "badge " + event.impact.toLowerCase(), event.impact));
        card.appendChild(top);

        var badges = el("div", "badges");
        if (next && event.id === next.id) badges.appendChild(el("span", "badge next", "Next"));
        if (past) badges.appendChild(el("span", "badge past", "Passed"));
        if (near.length) badges.appendChild(el("span", "badge session", sessionBadge(near)));
        if (badges.childNodes.length) card.appendChild(badges);

        card.appendChild(el("h3", null, event.title));
        var stats = el("dl", "stats");
        [["Forecast", event.forecast], ["Previous", event.previous]].forEach(function (pair) {
          var cell = el("div");
          cell.appendChild(el("dt", null, pair[0]));
          cell.appendChild(el("dd", null, pair[1] ? String(pair[1]) : "—"));
          stats.appendChild(cell);
        });
        card.appendChild(stats);
        card.appendChild(el("p", "note", event.goldNote || ""));
        card.appendChild(el("p", "source", event.source || ""));
        days.appendChild(card);
      });
    });

    if (!didScroll && nextNode) {
      didScroll = true;
      var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      nextNode.scrollIntoView({ block: "start", behavior: reduce ? "auto" : "smooth" });
    }
  }

  function tick() {
    var now = new Date().toISOString();
    clock.textContent = "Malaysia time now: " + GoldCalendar.formatDay(now) + ", " + GoldCalendar.formatTime(now);
  }

  toggle.addEventListener("click", function () {
    setMedium(!showMedium());
  });

  var stored = false;
  try {
    stored = localStorage.getItem("usd-news-show-medium") === "1";
  } catch (err) {
    stored = false;
  }
  setMedium(stored);
  tick();
  setInterval(tick, 30000);

  fetch("data/events.json", { cache: "no-store" })
    .then(function (response) {
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    })
    .then(function (data) {
      if (!data || !Array.isArray(data.events)) throw new Error("bad file");
      calendarData = data;
      render(data);
    })
    .catch(function () {
      status.hidden = false;
      status.textContent = "The event list could not be loaded. The calendar link below still works if the feed file is there. Nothing on this page is guessed.";
    });

  var copy = document.querySelector("#copy-feed");
  if (copy && navigator.clipboard) {
    copy.addEventListener("click", function () {
      navigator.clipboard.writeText(FEED_HTTPS).then(function () {
        copy.textContent = "Copied";
      }).catch(function () {
        copy.textContent = "Select the link and copy it";
      });
    });
  }
})();
