import { ICONS, STATES, STATE_ORDER } from "./states.js"

const $ = (sel, root = document) => root.querySelector(sel)

function pillLabel(bar) {
  if (!bar) return "Omalet"
  if (bar.label) return bar.label
  if (bar.charging) return bar.charging
  return `${ICONS.heart} ${bar.heart}  ${ICONS.air} ${bar.oxygen}`
}

function renderBar(state) {
  const pill = $("#owlet-pill")
  pill.textContent = ""
  const label = document.createElement("span")
  label.textContent = pillLabel(state.bar)
  pill.append(label)
  pill.classList.toggle("is-open", Boolean(state.panel))
  pill.classList.toggle("is-alert", Boolean(state.bar?.alert))
}

function tileEl(tile) {
  const el = document.createElement("article")
  el.className = "tile" + (tile.alert ? " is-alert" : "")
  const icon = document.createElement("span")
  icon.className = "tile-icon"
  icon.textContent = ICONS[tile.icon] || ""
  const copy = document.createElement("div")
  copy.className = "tile-copy"
  const value = document.createElement("div")
  value.className = "tile-value" + (tile.text ? " is-text" : "")
  value.textContent = tile.value
  const label = document.createElement("div")
  label.className = "tile-label"
  label.textContent = tile.label
  copy.append(value, label)
  el.append(icon, copy)
  return el
}

function renderPanel(state) {
  const panel = $("#panel")
  const bento = $("#bento")
  const charging = $("#charging")
  const login = $("#login")
  const alerts = $("#alerts")
  const kind = state.panel

  panel.style.display = kind ? "block" : "none"
  bento.style.display = kind === "bento" ? "grid" : "none"
  charging.style.display = kind === "charging" ? "block" : "none"
  login.style.display = kind === "login" ? "block" : "none"

  if (kind === "bento") {
    try {
      bento.replaceChildren(...state.tiles.map(tileEl))
    } catch (err) {
      bento.textContent = String(err)
    }
  }

  if (kind === "charging") {
    $("#charging-text").textContent = "Charging"
    ;[1, 2, 3].forEach((n) => {
      $(`.dot-${n}`).style.opacity = "1"
    })
  }

  alerts.replaceChildren()
  if (kind === "bento" && state.alerts?.length) {
    for (const line of state.alerts) {
      const p = document.createElement("p")
      p.className = "alert-line"
      p.textContent = line
      alerts.append(p)
    }
  }
}

export function applyState(id) {
  const state = STATES[id]
  if (!state) return
  document.body.dataset.state = id
  renderBar(state)
  renderPanel(state)
  for (const btn of document.querySelectorAll(".toolbar button")) {
    btn.setAttribute("aria-pressed", btn.dataset.state === id ? "true" : "false")
  }
}

export function boot() {
  const params = new URLSearchParams(location.search)
  if (params.has("capture")) document.body.classList.add("capture")
  $("#menu-icon").textContent = ICONS.menu
  $("#sys-icons").textContent = `${ICONS.bluetooth}  ${ICONS.wifi}  ${ICONS.volume}  ${ICONS.battery}`
  $("#charging-icon").textContent = ICONS.battery
  $("#login-go").textContent = ICONS.check

  const toolbar = $("#toolbar")
  for (const id of STATE_ORDER) {
    const btn = document.createElement("button")
    btn.type = "button"
    btn.dataset.state = id
    btn.textContent = STATES[id].title
    btn.addEventListener("click", () => {
      history.replaceState(null, "", `?state=${id}`)
      applyState(id)
    })
    toolbar.append(btn)
  }

  applyState(params.get("state") || "vitals")
  document.fonts.ready.then(() => {
    document.documentElement.dataset.ready = "1"
  })
}
