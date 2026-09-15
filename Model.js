function clean(value, fallback, maxLen) {
  var text = String(value == null ? "" : value).replace(/[\x00-\x1F\x7F]/g, "")
  text = text.replace(/^\s+|\s+$/g, "")
  if (text === "") return fallback == null ? "" : fallback
  var limit = maxLen || 80
  return text.length > limit ? text.slice(0, limit) : text
}

function emptyCamera() {
  return {
    present: false,
    id: "",
    name: "",
    status: "",
    source: "",
    snapshotPath: "",
    error: "",
    fetchedAt: 0,
    discoveredAt: 0
  }
}

function emptyState() {
  return {
    ok: false,
    status: "",
    error: "",
    needsLogin: false,
    fetchedAt: 0,
    label: "Owlet",
    sockName: "",
    connectionStatus: "",
    vitals: {},
    alerts: {},
    alertNames: [],
    alertCount: 0,
    camera: emptyCamera()
  }
}

function safeSnapshotPath(value) {
  var text = clean(value, "", 240)
  if (text === "" || text.indexOf("..") !== -1) return ""
  if (text.indexOf("owlet-camera.jpg") === -1) return ""
  if (text.charAt(0) !== "/") return ""
  return text
}

function parseCamera(raw) {
  var unset = emptyCamera()
  if (!raw || typeof raw !== "object") return unset
  var source = clean(raw.source, "", 16)
  if (source !== "url" && source !== "owlet") source = ""
  var status = clean(raw.status, "", 24)
  return {
    present: raw.present === true,
    id: clean(raw.id, "", 40),
    name: clean(raw.name, "", 40),
    status: status,
    source: source,
    snapshotPath: safeSnapshotPath(raw.snapshot_path || raw.snapshotPath),
    error: clean(raw.error, "", 80),
    fetchedAt: asInt(raw.fetched_at || raw.fetchedAt) || 0,
    discoveredAt: asInt(raw.discovered_at || raw.discoveredAt) || 0
  }
}

function asBool(value) {
  if (value === true || value === 1) return true
  if (value === false || value === 0 || value == null) return false
  var text = String(value).toLowerCase()
  return text === "true" || text === "1" || text === "yes" || text === "on"
}

function asInt(value) {
  if (value === undefined || value === null || value === "") return null
  var n = parseInt(String(value), 10)
  return isNaN(n) ? null : n
}

function parseState(raw) {
  var unset = emptyState()
  try {
    var data = JSON.parse(String(raw || ""))
    if (!data || typeof data !== "object") return unset

    var vitals = data.vitals && typeof data.vitals === "object" ? data.vitals : {}
    var alerts = data.alerts && typeof data.alerts === "object" ? data.alerts : {}
    var sock = data.sock && typeof data.sock === "object" ? data.sock : {}
    var alertNames = Array.isArray(data.alert_names) ? data.alert_names.map(function(name) {
      return clean(name, "", 40)
    }).filter(Boolean) : []

    var status = clean(data.status, "", 32)
    var label = clean(data.label, "Owlet", 24)
    return {
      ok: data.ok === true,
      status: status,
      error: clean(data.error, "", 160),
      needsLogin: data.needs_login === true,
      fetchedAt: asInt(data.fetched_at) || 0,
      label: label || "Owlet",
      sockName: clean(sock.name, "", 40),
      connectionStatus: clean(sock.connection_status, "", 24),
      vitals: {
        heartRate: asInt(vitals.heart_rate),
        oxygen: asInt(vitals.oxygen_saturation),
        oxygenAverage: asInt(vitals.oxygen_10_av),
        battery: asInt(vitals.battery_percentage),
        batteryMinutes: asInt(vitals.battery_minutes),
        signal: asInt(vitals.signal_strength),
        skinTempC: vitals.skin_temperature_c == null ? null : Number(vitals.skin_temperature_c),
        sleepLabel: clean(vitals.sleep_label, "", 24),
        movement: asBool(vitals.movement),
        charging: asBool(vitals.charging),
        baseOn: asBool(vitals.base_station_on),
        sockConnected: asBool(vitals.sock_connection),
        sockOff: asBool(vitals.sock_off),
        lastUpdated: clean(vitals.last_updated, "", 32)
      },
      alerts: alerts,
      alertNames: alertNames,
      alertCount: asInt(data.alert_count) || alertNames.length,
      camera: parseCamera(data.camera)
    }
  } catch (e) {
    return unset
  }
}

function statusTitle(state) {
  if (!state) return "Owlet"
  if (state.needsLogin) return "Sign in"
  if (state.status === "charging") return "Charging"
  if (state.status === "sock_off") return "Sock off"
  if (state.status === "offline") return "Offline"
  if (state.status === "monitoring") return "Monitoring"
  if (state.error) return "Can't reach Owlet"
  return "Owlet"
}

function statusDetail(state) {
  if (!state) return ""
  if (state.needsLogin) return "Click to store your Owlet password in the keyring"
  if (state.error) return state.error
  if (state.status === "charging") return "Vitals pause while the sock charges"
  if (state.status === "sock_off") return "Sock is off the foot"
  if (state.status === "offline") {
    // Check for base station status in sock connection details
    if (state.sock && state.sock.connection_status === "offline") {
      return "Base station is offline"
    }
    return "Base station or sock is not connected"
  }
  if (state.status === "monitoring") {
    if (state.vitals && state.vitals.sleepLabel) return state.vitals.sleepLabel
    return "Sock is reporting"
  }
  return ""
}

function displayNumber(value, fallback) {
  if (value === undefined || value === null || value === "") return fallback || "—"
  return String(value)
}

function batteryText(vitals) {
  if (!vitals || vitals.battery == null) return "—"
  var text = vitals.battery + "%"
  if (vitals.batteryMinutes && vitals.batteryMinutes > 0 && !vitals.charging)
    text += " · " + vitals.batteryMinutes + "m"
  return text
}

function temperatureText(vitals) {
  if (!vitals || vitals.skinTempC == null || isNaN(vitals.skinTempC)) return "—"
  return vitals.skinTempC + "°"
}

function movementText(vitals) {
  if (!vitals) return "—"
  return vitals.movement ? "moving" : "still"
}

function hasAlert(state) {
  return !!(state && state.alertCount > 0)
}

function emptyAlertTiles() {
  return {
    heart: false,
    oxygen: false,
    battery: false,
    temp: false,
    movement: false,
    sleep: false
  }
}

function isCharging(state) {
  return !!(state && (state.status === "charging" || (state.vitals && state.vitals.charging)))
}

function skipAlertWhenCharging(key) {
  return key === "sock_disconnected" || key === "sock_off"
}

function tileForAlert(key) {
  if (key === "critical_oxygen_alert" || key === "low_oxygen_alert" || key === "high_oxygen_alert") return "oxygen"
  if (key === "low_heart_rate_alert" || key === "high_heart_rate_alert") return "heart"
  if (key === "critical_battery_alert" || key === "low_battery_alert" || key === "lost_power_alert") return "battery"
  if (key === "sock_disconnected" || key === "sock_off") return "sleep"
  return ""
}

function alertTiles(state) {
  var tiles = emptyAlertTiles()
  if (!state || !state.alertNames || !state.alertNames.length) return tiles
  var charging = isCharging(state)
  for (var i = 0; i < state.alertNames.length; i++) {
    var key = state.alertNames[i]
    if (charging && skipAlertWhenCharging(key)) continue
    var tile = tileForAlert(key)
    if (tile) tiles[tile] = true
  }
  return tiles
}

function hasTileAlert(state) {
  var tiles = alertTiles(state)
  return !!(tiles.heart || tiles.oxygen || tiles.battery || tiles.temp || tiles.movement || tiles.sleep)
}

function showChargingPanel(state) {
  return isCharging(state) && !hasTileAlert(state)
}

function alertList(state) {
  if (!state || !state.alertNames || !state.alertNames.length) return []
  var labels = {
    critical_oxygen_alert: "Critical oxygen",
    low_oxygen_alert: "Low oxygen",
    high_oxygen_alert: "High oxygen",
    low_heart_rate_alert: "Low heart rate",
    high_heart_rate_alert: "High heart rate",
    critical_battery_alert: "Critical battery",
    low_battery_alert: "Low battery",
    lost_power_alert: "Base lost power",
    sock_disconnected: "Sock disconnected",
    sock_off: "Sock off"
  }
  var charging = isCharging(state)
  var out = []
  for (var i = 0; i < state.alertNames.length; i++) {
    var key = state.alertNames[i]
    if (charging && skipAlertWhenCharging(key)) continue
    out.push(labels[key] || key.replace(/_/g, " "))
  }
  return out
}

function heartIcon() {
  return "󰋑" // nf-md-heart
}

function airIcon() {
  return "󰖝" // nf-md-weather-windy
}

function batteryIcon() {
  return "󰁹" // nf-md-battery
}

function tempIcon() {
  return "󰔏" // nf-md-thermometer
}

function moveIcon() {
  return "󰖃" // nf-md-walk
}

function sleepIcon() {
  return "󰒲" // nf-md-sleep
}

function loginIcon() {
  return "󰍂" // nf-md-login
}

function logoutIcon() {
  return "󰍃" // nf-md-logout
}

function refreshIcon() {
  return "󰑐" // nf-md-refresh
}

function contextMenuItems(state, version, email, detached) {
  var loggedOut = !state || state.needsLogin === true
  var items = []
  items.push({
    id: loggedOut ? "login" : "logout",
    label: loggedOut ? "Sign in" : "Sign out",
    kind: "action",
    enabled: true
  })
  items.push({
    id: "refresh",
    label: "Refresh",
    kind: "action",
    enabled: true
  })
  items.push({
    id: detached ? "attach" : "detach",
    label: detached ? "Attach camera" : "Detach camera",
    kind: "action",
    enabled: true
  })
  items.push({ id: "separator", label: "", kind: "separator", enabled: false })
  var ver = clean(version, "", 24)
  items.push({
    id: "version",
    label: ver ? "Omalet " + ver : "Omalet",
    kind: "meta",
    enabled: false
  })
  var account = clean(email, "", 64)
  if (account && !loggedOut) {
    items.push({
      id: "account",
      label: account,
      kind: "meta",
      enabled: false
    })
  }
  return items
}

function cameraIcon() {
  return "󰄀" // nf-md-camera
}

function showCameraHero(state, showCameraSetting, hasUrl) {
  if (showCameraSetting === false) return false
  if (state && state.needsLogin) return false
  if (hasUrl) return true
  return !!(state && state.camera && state.camera.present)
}

function cameraAgeText(fetchedAt, nowSec) {
  var ts = asInt(fetchedAt)
  if (!ts) return ""
  var now = asInt(nowSec)
  if (!now) now = Math.floor(Date.now() / 1000)
  var age = now - ts
  if (age < 0) age = 0
  if (age < 15) return "just now"
  if (age < 90) return age + "s ago"
  var minutes = Math.round(age / 60)
  if (minutes < 60) return minutes + "m ago"
  return "stale"
}

function cameraCaption(state, nowSec, hasUrl) {
  var camera = state && state.camera ? state.camera : emptyCamera()
  if (camera.error) return camera.error
  var name = camera.name || (camera.source === "owlet" ? "Owlet Cam" : "Camera")
  if (camera.snapshotPath && camera.fetchedAt) {
    var age = cameraAgeText(camera.fetchedAt, nowSec)
    return age ? name + " · " + age : name
  }
  if (camera.present && !camera.snapshotPath) return name + " · no stills yet"
  if (hasUrl) return "Waiting for still"
  if (camera.status === "offline") return name + " · offline"
  if (camera.status === "none") return "No Owlet Cam on this account"
  return name
}

function barLabel(state, vertical) {
  if (!state) return "Owlet"
  if (state.status === "monitoring") {
    var hr = state.vitals && state.vitals.heartRate
    var ox = state.vitals && state.vitals.oxygen
    var hrText = hr > 0 ? String(hr) : "—"
    var oxText = ox > 0 ? String(ox) + "%" : "—"
    if (vertical) return heartIcon() + " " + hrText + "\n" + airIcon() + " " + oxText
    return heartIcon() + " " + hrText + "  " + airIcon() + " " + oxText
  }
  if (vertical) {
    if (state.status === "charging" && state.vitals && state.vitals.battery != null)
      return String(state.vitals.battery)
    return "Owlet"
  }
  return state.label || "Owlet"
}

if (typeof module !== "undefined") {
  module.exports = {
    clean: clean,
    emptyState: emptyState,
    emptyCamera: emptyCamera,
    asBool: asBool,
    asInt: asInt,
    parseState: parseState,
    parseCamera: parseCamera,
    safeSnapshotPath: safeSnapshotPath,
    statusTitle: statusTitle,
    statusDetail: statusDetail,
    displayNumber: displayNumber,
    batteryText: batteryText,
    temperatureText: temperatureText,
    movementText: movementText,
    hasAlert: hasAlert,
    alertTiles: alertTiles,
    hasTileAlert: hasTileAlert,
    showChargingPanel: showChargingPanel,
    isCharging: isCharging,
    alertList: alertList,
    barLabel: barLabel,
    showCameraHero: showCameraHero,
    cameraAgeText: cameraAgeText,
    cameraCaption: cameraCaption,
    heartIcon: heartIcon,
    airIcon: airIcon,
    batteryIcon: batteryIcon,
    tempIcon: tempIcon,
    moveIcon: moveIcon,
    sleepIcon: sleepIcon,
    loginIcon: loginIcon,
    logoutIcon: logoutIcon,
    refreshIcon: refreshIcon,
    cameraIcon: cameraIcon,
    contextMenuItems: contextMenuItems
  }
}
