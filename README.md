<div align="center">

# Omalet

**Owlet Smart Sock 3 vitals on the Omarchy bar.**

Heart rate and oxygen on the bar. A bento of vitals in the popup.
Desktop notifications when Owlet alert flags rise.

<img src="https://img.shields.io/badge/Omarchy-4.x-a855f7?style=flat-square" alt="Omarchy 4.x">
<img src="https://img.shields.io/badge/kind-bar--widget-22d3ee?style=flat-square" alt="bar-widget">
<img src="https://img.shields.io/badge/license-MIT-64748b?style=flat-square" alt="MIT">

<br><br>

<img src="preview.png" alt="Omalet vitals panel showing heart rate, blood oxygen, battery, skin temperature, movement, and sleep type" width="820">

</div>

Not affiliated with Owlet Baby Care. Uses the unofficial
[pyowletapi](https://github.com/ryanbdclark/pyowletapi) cloud client.
This is not a substitute for the official Owlet app or its alarms.

## Install

```bash
omarchy plugin add https://github.com/ravivasavan/Omalet.git --enable --yes
```

That clones the plugin, enables the bar widget, and the first refresh
creates a local Python venv with `pyowletapi`. Open the panel from the
bar pill, enter your Owlet email and password, and the password is stored
in the system keyring (`secret-tool`), not in `shell.json`.

Refresh interval is `refreshSeconds` on the bar entry (default 10).

## Remove

```bash
omarchy plugin remove ravivasavan.owlet --yes
```

That removes the plugin checkout and bar entry. It does not touch Hyprland
or other Omarchy config. Optional leftover cleanup:

```bash
rm -rf ~/.local/share/omarchy/owlet
rm -f ~/.local/state/omarchy/owlet.json \
      ~/.local/state/omarchy/owlet-tokens.json \
      ~/.local/state/omarchy/owlet-auth.json \
      ~/.local/state/omarchy/owlet-alerts.json
secret-tool clear service owlet
```

## What you see

| | |
|---|---|
| **Bar** | Heart rate and oxygen while the sock is monitoring |
| **Vitals panel** | Beats per minute, blood oxygen, battery level, skin temperature, movement, sleep type |
| **Charging** | The bento collapses to a single **Charging...** tile (dots animate one by one) |
| **Alerts** | The matching tile keeps the bento and softly pulses; a notification fires on rising flags |

Click the bar pill to open the panel. Middle-click refreshes. `r` refreshes
while the panel is focused.

## Dependencies

Already on a typical Omarchy install:

- Omarchy 4 / Omarchy shell (Quickshell)
- `python` (3.11+)
- `secret-tool` (`libsecret`)
- Network access to Owlet's cloud API

First run installs `pyowletapi==2025.4.10` into
`~/.local/share/omarchy/owlet/venv`. No sudo. No writes outside the plugin
directory, that venv, `~/.local/state/omarchy/owlet*`, and the keyring
item `service=owlet`.

## Privacy

- Password lives in the system keyring
- Session tokens live in `~/.local/state/omarchy/owlet-tokens.json` (mode 0600)
- Email/region live in `~/.local/state/omarchy/owlet-auth.json` (mode 0600)
- Nothing is uploaded except to Owlet's own API, through pyowletapi

## Screenshots

Tokyo Night on the Omarchy Quattro wallpaper. 16:9.

| Tray | Vitals |
| --- | --- |
| <img src="screenshots/tray.png" alt="Heart rate and oxygen on the bar" width="400"> | <img src="screenshots/vitals.png" alt="Six-tile vitals bento" width="400"> |

| Charging | Alert |
| --- | --- |
| <img src="screenshots/charging.png" alt="Charging tile" width="400"> | <img src="screenshots/alert.png" alt="Blood oxygen alert" width="400"> |

## Development

```
manifest.json    plugin declaration (kind: bar-widget)
BarWidget.qml    bar pill
Panel.qml        popup, login, charging tile, alert flash
StatBox.qml      one vitals tile
Model.js         state parsing and labels
fetch.py         unofficial Owlet poller
fetch.sh         venv bootstrap + poll
login.sh         keyring store + first poll
setup.sh         create venv, pin pyowletapi
test/run.js      node test/run.js
```

```bash
omarchy plugin validate ~/.config/omarchy/plugins/ravivasavan.owlet
node test/run.js
```

Saved edits under `~/.config/omarchy/plugins/` reload automatically.
Force a rescan with `omarchy-shell shell rescanPlugins`.

## License

MIT. Owlet is a trademark of Owlet Baby Care; this plugin is unofficial
and is not a medical device.
