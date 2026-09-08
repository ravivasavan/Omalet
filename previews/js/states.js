export const ICONS = {
  heart: "\u{F02D1}",
  air: "\u{F059D}",
  battery: "\u{F0079}",
  temp: "\u{F050F}",
  move: "\u{F0583}",
  sleep: "\u{F04B2}",
  check: "\u{F012C}",
  bluetooth: "\u{F00AF}",
  wifi: "\u{F0928}",
  volume: "\u{F057E}",
  menu: "\u{F02CA}",
}

const VITALS = {
  heart: { icon: "heart", value: "101", label: "Beats per minute" },
  oxygen: { icon: "air", value: "99%", label: "Blood Oxygen" },
  battery: { icon: "battery", value: "96%", label: "Battery Level" },
  temp: { icon: "temp", value: "33°", label: "Skin Temperature" },
  move: { icon: "move", value: "still", label: "Movement", text: true },
  sleep: { icon: "sleep", value: "light sleep", label: "Sleep Type", text: true },
}

function tiles(overrides = {}, alert = null) {
  return ["heart", "oxygen", "battery", "temp", "move", "sleep"].map((id) => ({
    id,
    ...VITALS[id],
    ...(overrides[id] || {}),
    alert: alert === id,
  }))
}

export const STATES = {
  tray: {
    title: "Tray",
    panel: false,
    bar: { heart: "101", oxygen: "99%" },
  },
  vitals: {
    title: "Vitals",
    panel: "bento",
    bar: { heart: "101", oxygen: "99%" },
    tiles: tiles(),
  },
  charging: {
    title: "Charging",
    panel: "charging",
    bar: { charging: "40%" },
    charging: "Charging...",
  },
  "alert-oxygen": {
    title: "Oxygen alert",
    panel: "bento",
    bar: { heart: "64", oxygen: "80%", alert: true },
    tiles: tiles(
      { heart: { value: "64" }, oxygen: { value: "80%" } },
      "oxygen",
    ),
    alerts: ["Low oxygen"],
  },
  "alert-heart": {
    title: "Heart-rate alert",
    panel: "bento",
    bar: { heart: "48", oxygen: "97%", alert: true },
    tiles: tiles(
      { heart: { value: "48" }, oxygen: { value: "97%" } },
      "heart",
    ),
    alerts: ["Low heart rate"],
  },
  "alert-battery": {
    title: "Battery alert",
    panel: "bento",
    bar: { heart: "101", oxygen: "99%", alert: true },
    tiles: tiles({ battery: { value: "8%" } }, "battery"),
    alerts: ["Low battery"],
  },
  "sock-off": {
    title: "Sock off",
    panel: "bento",
    bar: { label: "off" },
    tiles: tiles({
      heart: { value: "—" },
      oxygen: { value: "—" },
      temp: { value: "—" },
      move: { value: "—" },
      sleep: { value: "Sock off" },
    }),
  },
  login: {
    title: "Sign in",
    panel: "login",
    bar: { label: "Omalet" },
  },
}

export const STATE_ORDER = [
  "tray",
  "vitals",
  "charging",
  "alert-oxygen",
  "alert-heart",
  "alert-battery",
  "sock-off",
  "login",
]
