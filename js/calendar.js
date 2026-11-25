/* Shared clock math for the USD news page. Malaysia is UTC+8 all year. */
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  root.GoldCalendar = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  var WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  var MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
  ];
  var SESSIONS = [
    [15 * 60 + 30, "3:30 PM"],
    [21 * 60 + 30, "9:30 PM"]
  ];

  function pad(value) {
    return String(value).padStart(2, "0");
  }

  function mytParts(iso) {
    var ms = Date.parse(iso);
    if (Number.isNaN(ms)) {
      throw new Error("bad date");
    }
    var shifted = new Date(ms + 8 * 60 * 60 * 1000);
    return {
      year: shifted.getUTCFullYear(),
      month: shifted.getUTCMonth() + 1,
      day: shifted.getUTCDate(),
      hour: shifted.getUTCHours(),
      minute: shifted.getUTCMinutes()
    };
  }

  function dateKey(iso) {
    var parts = mytParts(iso);
    return parts.year + "-" + pad(parts.month) + "-" + pad(parts.day);
  }

  function addDays(key, days) {
    var bits = key.split("-").map(Number);
    var shifted = new Date(Date.UTC(bits[0], bits[1] - 1, bits[2] + days));
    return shifted.getUTCFullYear() + "-" + pad(shifted.getUTCMonth() + 1) + "-" + pad(shifted.getUTCDate());
  }

  function weekdaySunday0(key) {
    var bits = key.split("-").map(Number);
    return new Date(Date.UTC(bits[0], bits[1] - 1, bits[2])).getUTCDay();
  }

  function weekStartKey(iso) {
    var key = dateKey(iso);
    return addDays(key, -weekdaySunday0(key));
  }

  function inWindow(eventIso, nowIso) {
    var start = weekStartKey(nowIso);
    var key = dateKey(eventIso);
    return key >= start && key < addDays(start, 14);
  }

  function isPast(iso, nowMs) {
    return Date.parse(iso) < (nowMs == null ? Date.now() : nowMs);
  }

  function nearSessionLabels(iso) {
    var parts = mytParts(iso);
    var minutes = parts.hour * 60 + parts.minute;
    var labels = [];
    for (var i = 0; i < SESSIONS.length; i += 1) {
      var delta = Math.abs(minutes - SESSIONS[i][0]);
      if (delta > 720) {
        delta = 1440 - delta;
      }
      if (delta <= 30) {
        labels.push(SESSIONS[i][1]);
      }
    }
    return labels;
  }

  function formatTime(iso) {
    var hour = mytParts(iso).hour;
    var minute = mytParts(iso).minute;
    var suffix = hour >= 12 ? "PM" : "AM";
    var clock = hour % 12;
    if (clock === 0) {
      clock = 12;
    }
    return clock + ":" + pad(minute) + " " + suffix;
  }

  function formatDay(iso) {
    var parts = mytParts(iso);
    var key = parts.year + "-" + pad(parts.month) + "-" + pad(parts.day);
    return WEEKDAYS[weekdaySunday0(key)] + ", " + parts.day + " " + MONTHS[parts.month - 1];
  }

  function formatStamp(iso) {
    return formatDay(iso) + ", " + formatTime(iso) + " MYT";
  }

  return {
    mytParts: mytParts,
    dateKey: dateKey,
    addDays: addDays,
    weekStartKey: weekStartKey,
    inWindow: inWindow,
    isPast: isPast,
    nearSessionLabels: nearSessionLabels,
    formatTime: formatTime,
    formatDay: formatDay,
    formatStamp: formatStamp
  };
});
