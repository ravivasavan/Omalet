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

assert.strictEqual(monitoring.camera.present, false)
assert.strictEqual(Model.showCameraEnabled(null), true)
assert.strictEqual(Model.showCameraEnabled({}), true)
assert.strictEqual(Model.showCameraEnabled({ showCamera: true }), true)
assert.strictEqual(Model.showCameraEnabled({ showCamera: false }), false)
assert.strictEqual(Model.showCameraEnabled({ showCamera: 0 }), false)
assert.strictEqual(Model.showCameraHero(monitoring, true, false), false)
assert.strictEqual(Model.showCameraHero(monitoring, true, true), true)
assert.strictEqual(Model.showCameraHero(login, true, true), false)
assert.strictEqual(Model.showCameraHero(monitoring, false, true), false)
assert.strictEqual(Model.showCameraHero(monitoring, 0, true), false)

const withCamera = Model.parseState(JSON.stringify({
  ok: true,
  status: "monitoring",
  camera: {
    present: true,
    id: "OCA123",
    name: "Nursery",
    status: "online",
    source: "url",
    snapshot_path: "/home/ravi/.local/state/omarchy/owlet-camera.jpg",
    fetched_at: 1700000000,
    error: ""
  }
}))
assert.strictEqual(withCamera.camera.present, true)
assert.strictEqual(withCamera.camera.name, "Nursery")
assert.ok(withCamera.camera.snapshotPath.endsWith("owlet-camera.jpg"))
assert.strictEqual(Model.showCameraHero(withCamera, true, false), true)
assert.strictEqual(Model.cameraAgeText(1700000000, 1700000010), "just now")
assert.strictEqual(Model.cameraAgeText(1700000000, 1700000030), "30s ago")
assert.strictEqual(Model.cameraCaption(withCamera, 1700000030, true), "Nursery · 30s ago")

const noStills = Model.parseState(JSON.stringify({
  ok: true,
  status: "charging",
  camera: { present: true, name: "Owlet Cam", source: "owlet" }
}))
assert.strictEqual(Model.showCameraHero(noStills, true, false), true)
assert.strictEqual(Model.cameraCaption(noStills, 1700000000, false), "Owlet Cam · no stills yet")

const noCam = Model.parseState(JSON.stringify({
  camera: { source: "owlet", status: "none", present: false }
}))
assert.strictEqual(noCam.camera.status, "none")
assert.strictEqual(Model.cameraCaption(noCam, 1700000000, false), "No Owlet Cam on this account")
assert.strictEqual(Model.showCameraHero(noCam, true, false), false)

const evilCamera = Model.parseState(JSON.stringify({
  camera: {
    present: true,
    name: "Nursery\ncam",
    snapshot_path: "/tmp/../etc/passwd",
    error: "x".repeat(200),
    source: "javascript:alert(1)"
  }
}))
assert.ok(!evilCamera.camera.name.includes("\n"))
assert.strictEqual(evilCamera.camera.snapshotPath, "")
assert.ok(evilCamera.camera.error.length <= 80)
assert.strictEqual(evilCamera.camera.source, "")
assert.strictEqual(Model.safeSnapshotPath("/home/x/.local/state/omarchy/owlet-camera.jpg"), "/home/x/.local/state/omarchy/owlet-camera.jpg")
assert.strictEqual(Model.safeSnapshotPath("owlet-camera.jpg"), "")

const signedOutMenu = Model.contextMenuItems(login, "1.1.0", "parent@example.com")
assert.strictEqual(signedOutMenu[0].id, "login")
assert.strictEqual(signedOutMenu[0].label, "Sign in")
assert.strictEqual(signedOutMenu[1].id, "refresh")
assert.strictEqual(signedOutMenu[2].id, "hide-camera")
assert.strictEqual(signedOutMenu[2].label, "Hide camera")
assert.strictEqual(signedOutMenu[3].id, "detach")
assert.strictEqual(signedOutMenu[3].label, "Detach camera")
assert.strictEqual(signedOutMenu[4].kind, "separator")
assert.strictEqual(signedOutMenu[5].label, "Omalet 1.1.0")
assert.strictEqual(signedOutMenu.some(function(item) { return item.id === "account" }), false)

const attachedMenu = Model.contextMenuItems(monitoring, "1.1.0", "parent@example.com", true)
assert.strictEqual(attachedMenu[2].id, "hide-camera")
assert.strictEqual(attachedMenu[3].id, "attach")
assert.strictEqual(attachedMenu[3].label, "Attach camera")

const hiddenCameraMenu = Model.contextMenuItems(monitoring, "1.1.0", "parent@example.com", false, false)
assert.strictEqual(hiddenCameraMenu[2].id, "show-camera")
assert.strictEqual(hiddenCameraMenu[2].label, "Show camera")
assert.strictEqual(hiddenCameraMenu.some(function(item) { return item.id === "detach" || item.id === "attach" }), false)
assert.strictEqual(hiddenCameraMenu[3].kind, "separator")

const signedInMenu = Model.contextMenuItems(monitoring, "1.1.0", "parent@example.com")
assert.strictEqual(signedInMenu[0].id, "logout")
assert.strictEqual(signedInMenu[0].label, "Sign out")
assert.strictEqual(signedInMenu[signedInMenu.length - 1].id, "account")
assert.strictEqual(signedInMenu[signedInMenu.length - 1].label, "parent@example.com")

const fallbackMenu = Model.contextMenuItems(null, "", "")
assert.strictEqual(fallbackMenu[0].id, "login")
assert.strictEqual(fallbackMenu[2].id, "hide-camera")
assert.strictEqual(fallbackMenu[3].id, "detach")
assert.strictEqual(fallbackMenu[5].label, "Omalet")
assert.strictEqual(fallbackMenu.some(function(item) { return item.id === "account" }), false)

console.log("ok")
