const assert = require("assert");
const cal = require("../js/calendar.js");

function same(actual, expected, label) {
  assert.deepStrictEqual(actual, expected, label || "");
}

const now = "2026-11-25T06:00:00Z";

same(cal.formatTime("2026-11-25T13:30:00Z"), "9:30 PM", "PCE is 9:30 PM MYT");
same(cal.dateKey("2026-11-25T13:30:00Z"), "2026-11-25");
same(cal.nearSessionLabels("2026-11-25T13:30:00Z"), ["9:30 PM"]);
same(cal.formatTime("2026-11-25T07:30:00Z"), "3:30 PM");
same(cal.nearSessionLabels("2026-11-25T07:30:00Z"), ["3:30 PM"]);
same(cal.nearSessionLabels("2026-11-25T07:00:00Z"), ["3:30 PM"], "3:00 PM is 30 min before");
same(cal.nearSessionLabels("2026-11-25T06:59:00Z"), [], "2:59 PM is outside");
same(cal.nearSessionLabels("2026-11-25T08:00:00Z"), ["3:30 PM"], "4:00 PM is 30 min after");
same(cal.nearSessionLabels("2026-11-25T08:01:00Z"), []);
same(cal.nearSessionLabels("2026-11-25T14:00:00Z"), ["9:30 PM"], "10:00 PM boundary");
same(cal.nearSessionLabels("2026-11-25T14:01:00Z"), []);
same(cal.nearSessionLabels("2026-12-01T15:00:00Z"), [], "11:00 PM is 90 min after 9:30");
same(cal.formatTime("2026-11-25T04:00:00Z"), "12:00 PM");
same(cal.formatTime("2026-11-25T16:00:00Z"), "12:00 AM");
same(cal.dateKey("2026-11-25T16:00:00Z"), "2026-11-26");
same(cal.formatDay("2026-11-25T13:30:00Z"), "Wednesday, 25 November");

same(cal.weekStartKey(now), "2026-11-22");
assert.strictEqual(cal.inWindow("2026-11-21T16:00:00Z", now), true, "Sunday 00:00 MYT is inside");
assert.strictEqual(cal.inWindow("2026-11-21T15:59:00Z", now), false, "Saturday before is outside");
assert.strictEqual(cal.inWindow("2026-12-05T15:59:00Z", now), true, "end of next Saturday is inside");
assert.strictEqual(cal.inWindow("2026-12-05T16:00:00Z", now), false, "the Sunday after next week is outside");
assert.strictEqual(cal.isPast("2026-11-25T05:00:00Z", Date.parse(now)), true);
assert.strictEqual(cal.isPast("2026-11-25T07:00:00Z", Date.parse(now)), false);

console.log("calendar.js ok");
