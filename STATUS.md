# Status — Owlet Cam stills (not on main)

Branch for the in-progress camera work. Do not merge to `main` until a still
actually lands in the bento.

## What landed on this branch

- Left-click the bar pill opens the vitals bento. Right-click opens a context
  menu (sign in / sign out, refresh, show/hide camera, detach camera, version,
  account email). Middle-click still refreshes. Hide camera drops the still
  from the bento and stops fetching; it writes `showCamera: false` on the
  bar entry.
- Sign-out clears the keyring, tokens, alerts, and camera still; keeps the
  saved email.
- Optional 16:9 camera tile above the bento (`CameraTile.qml`). Detach pops
  it into a floating, pinned Hyprland window titled `Omalet Camera` so you
  can keep watching while you work. Stills refresh every 15s while the panel
  or the detached window is open.
- Native Owlet Cam discovery: the cloud device list only returns the sock.
  The cam is found on the LAN by reverse-DNS (`OwletCam-OCC….lan`). Display
  name is **Arlo's camera**, id `OCC2381092200014`.
- Native still grab over TUTK P2P (`tutk_snapshot.py`) when no
  `cameraSnapshotUrl` is set. Credentials come from Owlet camera-kms
  (`GET /kms/{OCC id}` → tutkid, authKey, password).

## Where stills are stuck

Omalet **does request** a frame now. The grab fails with **Camera P2P timed
out** (`IOTC_ER_TIMEOUT` / -13).

Facts from the live setup:

| | |
|---|---|
| Sock | `192.168.8.186` (Murata / Ayla), vitals work |
| Cam | `192.168.8.119`, hostname `OwletCam-OCC2381092200014.lan`, firmware 4.2.146 |
| This PC | Ethernet `192.168.1.109` (default route) + Travel Wifi `192.168.8.132` |
| Travel router | GL-BE3600 at `192.168.8.1`, SSID **Vasavan Travel Wifi**, NAT in front of the cam |
| TUTK cloud | `IOTC_Check_Device_OnlineEx` succeeds; cam is online |
| LAN | ICMP to the cam works. No HTTP, no RTSP, no UDP replies on 32761 / 63616 |
| Phone app | Closed on the owner's phone; another viewer may still be possible |

The cam only speaks ThroughTek TUTK (no JPEG URL). Cloud P2P from this
dual-homed PC never finishes a session, even with a 40s timeout, LAN bind
to `wlo2`, and broadcast redirected at the cam. That matches a second NAT
plus no LAN TUTK listener, not a missing fetch in the widget.

## Local files not in git

These stay on the machine only:

- `~/.local/share/omarchy/owlet/lib/libIOTCAPIs_ALL.so` — TUTK 4.2.1.1
- `~/.local/share/omarchy/owlet/tutk.key` — TUTK SDK license used to init the lib
- `~/.local/state/omarchy/owlet-firebase.key` — Owlet Care Firebase web API key (mode 0600). Optional; only used for the cloud device list. LAN discovery does not need it. Override with `OWLET_FIREBASE_WEB_KEY`.
- `~/.local/state/omarchy/owlet-camera.json` — cam id, IP, **P2P secrets** (mode 0600)
- `~/.config/hypr/hyprland.lua` — window rule: float + pin title `^Omalet Camera$`

## Next session

1. Put the GL-BE3600 in **Access Point / Extender** mode so the cam lands on
   `192.168.1.x` next to this PC (no travel-router NAT).
2. Retry `fetch.py --camera` / open the bento. If P2P connects, decode one
   H.264/HEVC frame to `~/.local/state/omarchy/owlet-camera.jpg`.
3. Only then merge this branch to `main`.

HTTP `cameraSnapshotUrl` (go2rtc / Home Assistant) still works as a bypass
if a JPEG endpoint shows up first.
