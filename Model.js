function clean(value, fallback, maxLen) {
  var text = String(value == null ? "" : value).replace(/[\x00-\x1F\x7F]/g, "")
  text = text.replace(/^\s+|\s+$/g, "")
  if (text === "") return fallback == null ? "" : fallback
  var limit = maxLen || 80
  return text.length > limit ? text.slice(0, limit) : text
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
    alertCount: 0
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
      alertCount: asInt(data.alert_count) || alertNames.length
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
  if (state.status === "offline") return "Base station or sock is not connected"
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
    asBool: asBool,
    asInt: asInt,
    parseState: parseState,
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
    heartIcon: heartIcon,
    airIcon: airIcon,
    batteryIcon: batteryIcon,
    tempIcon: tempIcon,
    moveIcon: moveIcon,
    sleepIcon: sleepIcon,
    loginIcon: loginIcon
  }
}
