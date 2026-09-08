const assert = require("assert")
const Model = require("../Model.js")

const monitoring = Model.parseState(JSON.stringify({
  ok: true,
  status: "monitoring",
  error: "",
  needs_login: false,
  fetched_at: 1700000000,
  label: "128  98%",
  sock: { name: "Owlet Baby Monitors", connection_status: "Online" },
  vitals: {
    heart_rate: 128,
    oxygen_saturation: 98,
    battery_percentage: 82,
    battery_minutes: 400,
    skin_temperature_c: 34.2,
    sleep_label: "light sleep",
    movement: 0,
    charging: 0,
    base_station_on: 1,
    sock_connection: 1,
    sock_off: false
  },
  alerts: { low_oxygen_alert: false, sock_off: false },
  alert_names: [],
  alert_count: 0
}))

assert.strictEqual(monitoring.ok, true)
assert.strictEqual(monitoring.status, "monitoring")
assert.strictEqual(monitoring.vitals.heartRate, 128)
assert.strictEqual(monitoring.vitals.oxygen, 98)
assert.strictEqual(Model.barLabel(monitoring, false), Model.heartIcon() + " 128  " + Model.airIcon() + " 98%")
assert.strictEqual(Model.barLabel(monitoring, true), Model.heartIcon() + " 128\n" + Model.airIcon() + " 98%")
assert.strictEqual(Model.statusTitle(monitoring), "Monitoring")
assert.strictEqual(Model.batteryText(monitoring.vitals), "82% · 400m")
assert.strictEqual(Model.temperatureText(monitoring.vitals), "34.2°")
assert.strictEqual(Model.movementText(monitoring.vitals), "still")
assert.strictEqual(Model.hasAlert(monitoring), false)

const evil = Model.parseState(JSON.stringify({
  ok: true,
  status: "monitoring\nrm -rf /",
  label: "128\x07  98%",
  error: "x".repeat(200),
  vitals: {},
  alert_names: ["low_oxygen_alert", "not_a_real\nalert"]
}))
assert.ok(!evil.status.includes("\n"))
assert.ok(!evil.label.includes("\x07"))
assert.ok(evil.error.length <= 160)

const alerts = Model.parseState(JSON.stringify({
  ok: true,
  status: "monitoring",
  label: "64  80%",
  alerts: { low_oxygen_alert: true },
  alert_names: ["low_oxygen_alert"],
  alert_count: 1,
  vitals: { heart_rate: 64, oxygen_saturation: 80 }
}))
assert.strictEqual(Model.hasAlert(alerts), true)
assert.deepStrictEqual(Model.alertList(alerts), ["Low oxygen"])

const login = Model.parseState(JSON.stringify({
  ok: false,
  status: "needs_login",
  needs_login: true,
  error: "Sign in to Owlet to show sock vitals",
  label: "Owlet"
}))
assert.strictEqual(login.needsLogin, true)
assert.strictEqual(Model.statusTitle(login), "Sign in")
assert.strictEqual(Model.parseState("not-json").label, "Owlet")

const charging = Model.parseState(JSON.stringify({
  ok: true,
  status: "charging",
  vitals: { charging: 1, battery_percentage: 40, sock_off: true },
  alerts: { sock_off: true },
  alert_names: ["sock_off"],
  alert_count: 1
}))
assert.strictEqual(Model.showChargingPanel(charging), true)
assert.strictEqual(Model.alertTiles(charging).sleep, false)
assert.deepStrictEqual(Model.alertList(charging), [])

const chargingOxygen = Model.parseState(JSON.stringify({
  ok: true,
  status: "charging",
  vitals: { charging: 1, oxygen_saturation: 80 },
  alerts: { low_oxygen_alert: true, sock_off: true },
  alert_names: ["low_oxygen_alert", "sock_off"],
  alert_count: 2
}))
assert.strictEqual(Model.showChargingPanel(chargingOxygen), false)
assert.strictEqual(Model.alertTiles(chargingOxygen).oxygen, true)
assert.strictEqual(Model.alertTiles(chargingOxygen).heart, false)
assert.deepStrictEqual(Model.alertList(chargingOxygen), ["Low oxygen"])

const oxygenTiles = Model.alertTiles(alerts)
assert.strictEqual(oxygenTiles.oxygen, true)
assert.strictEqual(oxygenTiles.heart, false)
assert.strictEqual(Model.showChargingPanel(monitoring), false)

console.log("ok")
