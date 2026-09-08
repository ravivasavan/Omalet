# Omalet preview studio

Headless Tokyo Night desktop that renders the bar pill and every bento
state over the Omarchy Quattro wallpaper.

```
css/tokens.css   Tokyo Night + Omarchy 12px spacing scale
css/bar.css      transparent top bar + owlet pill
css/panel.css    KeyboardPanel chrome, tiles, charging, login
js/states.js     tray, vitals, charging, alerts, sock-off, login
js/render.js     applies a state to the scene
capture.sh       4:3 PNG export at 2400×1800
```

```bash
# Interactive
python3 -m http.server 8765 --bind 127.0.0.1
# then http://127.0.0.1:8765/?state=vitals

# Export into ../preview.png and ../screenshots/
./capture.sh
```
