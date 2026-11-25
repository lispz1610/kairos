const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const html = fs.readFileSync(
  path.join(__dirname, "../../src/adapters/web/templates/index.html"), "utf8"
).replace(/\r\n/g, "\n");

function install(context, name) {
  const pattern = new RegExp(`(?:async )?function ${name}\\(`);
  const match = pattern.exec(html);
  assert.ok(match, `${name} should exist`);
  const end = html.indexOf("\n}\n", match.index);
  assert.ok(end > match.index);
  vm.runInContext(html.slice(match.index, end + 2), context);
}

test("the seeded timeline belongs to a TripDay", () => {
  const context = vm.createContext({});
  for (const name of ["parseDate", "makeTripDays", "defaultTrip", "defaultStop", "defaultState"]) {
    install(context, name);
  }
  const trip = vm.runInContext("defaultTrip()", context);
  context.loadTrip = () => trip;
  const state = vm.runInContext("defaultState()", context);
  assert.equal(state.day_id, `dia-${state.current_time.slice(0, 10)}`);
  assert.ok(trip.stages.some((stage) => stage.days.some(
    (day) => day.date === state.current_time.slice(0, 10)
  )));
  assert.ok(state.itinerary.every((stop) =>
    stop.start.slice(0, 10) === state.current_time.slice(0, 10)
  ));
  context.loadTrip = () => ({ stages: [] });
  assert.equal(vm.runInContext("defaultState().current_time", context), "2026-11-01T09:00:00");
});

test("replanning sends reservations and saves the matching TripDay", async () => {
  const visit = {
    poi: { id: "museum", name: "Museu", coordinates: [-23.55, -46.63] },
    start: "2026-11-01T09:00:00", duration_minutes: 60,
  };
  const restaurant = { id: "lunch", name: "Almoço", coordinates: [-23.55, -46.63] };
  const day = {
    date: "2026-11-01", meal_slots: [{
      window: { start_time: "12:00:00", end_time: "13:00:00" },
      selected_place: restaurant,
    }],
  };
  const trip = { stages: [
    { id: "stage-a", days: [day] },
    { id: "stage-b", days: [{ date: "2026-11-02" }] },
  ] };
  const state = {
    day_id: "dia-2026-11-01", current_time: "2026-11-01T10:00:00",
    itinerary: [visit], availability_window: { start: "08:00", end: "18:00" },
    reserved_future_stops: [], closed_pois: [], skipped_pois: [],
    intercity_connection: null, travel_time_minutes: 15, selectedIndex: 0,
  };
  let sent;
  let savedTrip;
  const context = vm.createContext({
    document: { getElementById: () => ({ value: "stage-b" }) },
    loadState: () => state,
    loadTrip: () => trip,
    saveTrip: (value) => { savedTrip = value; },
    saveState: () => {},
    currentCoordinate: () => [-23.55, -46.63],
    renderTimeline: () => {}, updateMapRoute: () => {}, showBanner: () => {},
    fetch: async (_, options) => {
      sent = JSON.parse(options.body);
      return { ok: true, json: async () => ({ itinerary: [visit], removed_pois: [], intercity_risk_alert: null }) };
    },
    API_URL: "/api/trip/replan",
  });
  for (const name of ["tripDay", "slotWindowBounds", "futureMealSlots", "futureReservedStops", "selectUpcoming", "replan"]) {
    install(context, name);
  }
  await vm.runInContext(
    "replan([{ type: 'delay', delay_minutes: 0 }], (updated) => { updated.current_time = '2026-11-02T00:05:00'; })",
    context
  );
  assert.deepEqual(sent.reserved_meal_slots, [day.meal_slots[0].window]);
  assert.deepEqual(sent.reserved_future_stops, [{
    poi: restaurant, start: "2026-11-01T12:00:00", duration_minutes: 60,
  }]);
  assert.deepEqual(savedTrip.stages[0].days[0].itinerary.stops, [visit]);
  assert.equal(savedTrip.stages[1].days[0].itinerary, undefined);
  assert.deepEqual(vm.runInContext("futureReservedStops(loadState())", context), []);
});

test("post-delay wall-clock time keeps TripDay and future meal slots in non-UTC timezones", () => {
  const { execFileSync } = require("node:child_process");
  const script = `
    const assert = require("node:assert/strict");
    const fs = require("node:fs");
    const vm = require("node:vm");
    const html = fs.readFileSync(${JSON.stringify(
      path.join(__dirname, "../../src/adapters/web/templates/index.html")
    )}, "utf8").replace(/\\r\\n/g, "\\n");
    function install(context, name) {
      const match = new RegExp("(?:async )?function " + name + "\\\\(").exec(html);
      assert.ok(match, name + " should exist");
      const end = html.indexOf("\\n}\\n", match.index);
      vm.runInContext(html.slice(match.index, end + 2), context);
    }
    const restaurant = { id: "dinner", name: "Jantar", coordinates: [-23.55, -46.63] };
    const day = {
      date: "2026-11-01",
      meal_slots: [
        { window: null, selected_place: restaurant },
        { window: { start_time: "22:30:00", end_time: "23:30:00" }, selected_place: restaurant },
      ],
    };
    const trip = { stages: [{ id: "stage-a", days: [day, { date: "2026-11-02", meal_slots: [] }] }] };
    const state = {
      current_time: "2026-11-01T21:15:00",
      reserved_future_stops: [],
    };
    const context = vm.createContext({ loadTrip: () => trip });
    for (const name of ["addMinutes", "tripDay", "slotWindowBounds", "futureMealSlots", "futureReservedStops"]) {
      install(context, name);
    }
    state.current_time = context.addMinutes(state.current_time, 30);
    assert.equal(state.current_time, "2026-11-01T21:45:00");
    assert.equal(context.tripDay(trip, state).date, "2026-11-01");
    assert.deepEqual(
      JSON.parse(JSON.stringify(context.futureMealSlots(state))),
      [day.meal_slots[1].window]
    );
    assert.deepEqual(
      JSON.parse(JSON.stringify(context.futureReservedStops(state))),
      [{
        poi: restaurant,
        start: "2026-11-01T22:30:00",
        duration_minutes: 60,
      }]
    );
  `;
  execFileSync(process.execPath, ["-e", script], {
    env: { ...process.env, TZ: "America/Sao_Paulo" },
    stdio: "pipe",
  });
});
