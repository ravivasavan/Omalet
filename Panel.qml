import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "Model.js" as Model

Panel {
  id: root
  moduleName: "ravivasavan.owlet"
  ipcTarget: "ravivasavan.owlet"
  manageIpc: false

  property var anchorItem: null
  property bool openedFromHotkey: false
  property var hostWidget: null
  readonly property var barIdentity: hostWidget || root

  property var state: Model.emptyState()
  property string label: "Owlet"
  readonly property bool alarming: Model.hasAlert(state)
  readonly property bool needsLogin: state.needsLogin === true
  readonly property var vitals: state.vitals || {}
  readonly property var alertLines: Model.alertList(state)
  readonly property string statusTitle: Model.statusTitle(state)
  readonly property string statusDetail: Model.statusDetail(state)
  // Popup text must use the flyout surface role, not barForeground.
  // A transparent bar picks a dark contrast color against light wallpaper;
  // that color is unreadable on the dark popup card.
  readonly property color fg: Color.popups.text
  readonly property color dim: Qt.darker(Color.popups.text, 1.3)
  readonly property color alertColor: Color.urgent
  readonly property string uiFont: bar ? bar.fontFamily : Style.font.family
  readonly property int refreshSeconds: Math.max(5, Math.min(60, parseInt(setting("refreshSeconds", 10), 10) || 10))
  readonly property bool showCamera: Model.showCameraEnabled(settings)
  readonly property string cameraSnapshotUrl: String(setting("cameraSnapshotUrl", "") || "").replace(/^\s+|\s+$/g, "")
  readonly property bool cameraUrlReady: cameraSnapshotUrl.indexOf("http://") === 0 || cameraSnapshotUrl.indexOf("https://") === 0
  readonly property var camera: state.camera || {}
  readonly property bool showCameraHero: Model.showCameraHero(state, root.showCamera, root.cameraUrlReady)
  readonly property bool watchingCamera: root.opened || root.detached
  readonly property bool nativeCameraReady: root.camera.source === "owlet" && root.camera.present === true
  readonly property string cameraSnapshotSource: {
    if (!root.watchingCamera || !root.camera.snapshotPath) return ""
    return "file://" + root.camera.snapshotPath
  }
  readonly property string cameraFloatCaption: {
    var hr = root.vitals.heartRate
    var ox = root.vitals.oxygen
    var vit = ""
    if (hr > 0 || ox > 0)
      vit = (hr > 0 ? String(hr) : "—") + "  " + (ox > 0 ? String(ox) + "%" : "—") + " · "
    return vit + Model.cameraCaption(root.state, root.nowSec, root.cameraUrlReady)
  }
  property int nowSec: Math.floor(Date.now() / 1000)
  readonly property string pluginDir: Quickshell.env("HOME") + "/.config/omarchy/plugins/ravivasavan.owlet"
  readonly property string statePath: Quickshell.env("HOME") + "/.local/state/omarchy/owlet.json"
  readonly property string authPath: Quickshell.env("HOME") + "/.local/state/omarchy/owlet-auth.json"
  property string savedEmail: ""
  property string pluginVersion: ""
  property bool menuOpen: false
  property var menuItems: []
  property bool detached: false

  readonly property color tileFill: Style.normalFillFor(root.fg, Color.accent)
  readonly property bool monitoring: state.status === "monitoring"
  readonly property var alertFlags: Model.alertTiles(state)
  readonly property bool showCharging: Model.showChargingPanel(state)
  property bool loginBusy: false
  property string loginError: ""
  property int chargingDotStep: 0

  function open() {
    openedFromHotkey = false
    root.closeMenu()
    root.controller.show()
    stateFile.reload()
    root.refresh()
  }

  function openFromHotkey() {
    openedFromHotkey = true
    root.open()
  }

  function close() {
    root.closeMenu()
    root.controller.hide()
  }

  function closeMenu() {
    root.menuOpen = false
  }

  function toggle() {
    if (root.menuOpen) {
      root.closeMenu()
      if (!root.opened) root.open()
      return
    }
    if (root.opened) root.close()
    else root.open()
  }

  function toggleMenu() {
    if (root.menuOpen) {
      root.closeMenu()
      return
    }
    root.menuItems = Model.contextMenuItems(state, pluginVersion, savedEmail, root.detached, root.showCamera)
    if (root.opened) root.controller.hide()
    root.menuOpen = true
  }

  function switchPanel(direction) {
    if (root.bar && typeof root.bar.switchPanelFrom === "function")
      return root.bar.switchPanelFrom(root.barIdentity, direction)
    return false
  }

  function applyState(raw) {
    var parsed = Model.parseState(raw)
    root.state = parsed
    root.label = Model.barLabel(parsed, root.bar && root.bar.vertical)
  }

  function refresh() {
    if (!fetchProc.running) fetchProc.running = true
    root.refreshCamera()
  }

  function refreshCamera() {
    if (!root.watchingCamera || !root.showCamera) return
    if (!root.cameraUrlReady && !root.nativeCameraReady) return
    if (cameraProc.running) return
    cameraProc.secret = root.cameraUrlReady ? root.cameraSnapshotUrl : ""
    cameraProc.running = true
  }

  function detachCamera() {
    root.closeMenu()
    root.detached = true
    if (root.opened) root.controller.hide()
  }

  function attachCamera() {
    root.detached = false
    if (!root.opened) root.open()
  }

  function signIn() {
    root.closeMenu()
    if (!root.opened) root.open()
    Qt.callLater(function() {
      if (emailField && String(emailField.text || "") === "") emailField.forceActiveFocus()
      else if (passwordField) passwordField.forceActiveFocus()
    })
  }

  function signOut() {
    if (logoutProc.running) return
    logoutProc.running = true
  }

  function persistSettings(values) {
    var entry = { id: root.moduleName }
    for (var existing in root.settings) if (existing !== "id") entry[existing] = root.settings[existing]
    for (var key in values) entry[key] = values[key]
    root.settings = entry
    if (root.hostWidget && "settings" in root.hostWidget) root.hostWidget.settings = entry
    if (root.bar && root.bar.shell && typeof root.bar.shell.updateEntryInline === "function")
      root.bar.shell.updateEntryInline(root.moduleName, entry)
  }

  function setShowCamera(on) {
    root.persistSettings({ showCamera: !!on })
    root.closeMenu()
    if (!on) root.detached = false
    else root.refreshCamera()
  }

  function chooseMenu(itemId) {
    if (itemId === "login") root.signIn()
    else if (itemId === "logout") root.signOut()
    else if (itemId === "refresh") {
      root.closeMenu()
      root.refresh()
    } else if (itemId === "hide-camera") root.setShowCamera(false)
    else if (itemId === "show-camera") root.setShowCamera(true)
    else if (itemId === "detach") root.detachCamera()
    else if (itemId === "attach") root.attachCamera()
  }

  function submitPassword() {
    var email = emailField ? String(emailField.text || "").replace(/^\s+|\s+$/g, "") : ""
    var pw = passwordField ? String(passwordField.text || "") : ""
    if (email === "") {
      if (emailField) emailField.forceActiveFocus()
      return
    }
    if (pw === "" || loginProc.running) {
      if (passwordField) passwordField.forceActiveFocus()
      return
    }
    root.loginBusy = true
    root.loginError = ""
    loginProc.secret = email + "\n" + pw
    passwordField.text = ""
    loginProc.running = true
  }

  FileView {
    id: stateFile
    path: root.statePath
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: root.applyState(text())
    onLoadFailed: root.applyState("")
  }

  FileView {
    id: authFile
    path: root.authPath
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: {
      try {
        var data = JSON.parse(text())
        root.savedEmail = data && data.email ? String(data.email) : ""
        if (emailField && emailField.text === "" && root.savedEmail !== "")
          emailField.text = root.savedEmail
      } catch (e) {
        root.savedEmail = ""
      }
    }
    onLoadFailed: root.savedEmail = ""
  }

  FileView {
    id: manifestFile
    path: root.pluginDir + "/manifest.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: {
      try {
        var data = JSON.parse(text())
        root.pluginVersion = data && data.version ? String(data.version) : ""
      } catch (e) {
        root.pluginVersion = ""
      }
    }
    onLoadFailed: root.pluginVersion = ""
  }

  Process {
    id: fetchProc
    command: [root.pluginDir + "/fetch.sh"]
    onExited: stateFile.reload()
  }

  Process {
    id: cameraProc
    property string secret: ""
    command: [root.pluginDir + "/fetch.sh", "--camera"]
    stdinEnabled: true
    onStarted: {
      write(secret + "\n")
      secret = ""
    }
    onExited: stateFile.reload()
  }

  Process {
    id: loginProc
    property string secret: ""
    command: [root.pluginDir + "/login.sh"]
    stdinEnabled: true
    onStarted: {
      write(secret + "\n")
      secret = ""
    }
    onExited: function(exitCode) {
      root.loginBusy = false
      stateFile.reload()
      if (exitCode !== 0) {
        root.loginError = root.state.error || "Could not sign in"
        if (passwordField) passwordField.forceActiveFocus()
      }
    }
  }

  Process {
    id: logoutProc
    command: [root.pluginDir + "/fetch.sh", "--logout"]
    onExited: {
      stateFile.reload()
      root.closeMenu()
      root.detached = false
    }
  }

  Timer {
    interval: 1500
    running: true
    onTriggered: stateFile.reload()
  }

  Timer {
    interval: root.refreshSeconds * 1000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  Timer {
    interval: 450
    running: root.opened && root.showCharging && !root.needsLogin
    repeat: true
    onRunningChanged: if (running) root.chargingDotStep = 1
    onTriggered: root.chargingDotStep = root.chargingDotStep >= 3 ? 1 : root.chargingDotStep + 1
  }

  Timer {
    interval: 15000
    running: root.watchingCamera && root.showCamera && (root.cameraUrlReady || root.nativeCameraReady)
    repeat: true
    onTriggered: root.refreshCamera()
  }

  Timer {
    interval: 1000
    running: root.watchingCamera && root.showCameraHero
    repeat: true
    triggeredOnStart: true
    onTriggered: root.nowSec = Math.floor(Date.now() / 1000)
  }

  IpcHandler {
    target: root.ipcTarget

    function open(): void { root.openFromHotkey() }
    function close(): void { root.close() }
    function show(): void { root.openFromHotkey() }
    function hide(): void { root.close() }
    function toggle(): void { root.toggle() }
    function refresh(): void { root.refresh() }
    function login(): void { root.signIn() }
    function logout(): void { root.signOut() }
    function detach(): void { root.detachCamera() }
    function attach(): void { root.attachCamera() }
    function hideCamera(): void { root.setShowCamera(false) }
    function showCamera(): void { root.setShowCamera(true) }
  }

  Item {
    id: menuOwner
    function close() { root.closeMenu() }
    function closeForPopoutSwitch() { root.closeMenu() }
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(320))
    contentHeight: panel.fittedContentHeight(owletColumn.implicitHeight)

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      blocked: root.needsLogin
      onReturnRequested: root.needsLogin ? root.submitPassword() : root.refresh()
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onTextKey: function(t) {
        if (t === "r" || t === "R") root.refresh()
      }

      Column {
        id: owletColumn
        width: parent.width
        spacing: Style.space(8)

        Item {
          visible: root.showCameraHero && !root.detached
          width: parent.width
          implicitHeight: cameraHero.implicitHeight

          CameraTile {
            id: cameraHero
            width: parent.width
            icon: Model.cameraIcon()
            caption: Model.cameraCaption(root.state, root.nowSec, root.cameraUrlReady)
            hasImage: !!(root.camera.snapshotPath && root.cameraSnapshotSource !== "")
            imageSource: root.cameraSnapshotSource
            reloadToken: root.camera.fetchedAt || 0
            fg: root.fg
            dim: root.dim
            fill: root.tileFill
            fontFamily: root.uiFont
          }

          PanelActionButton {
            anchors.top: parent.top
            anchors.right: parent.right
            anchors.topMargin: Style.space(6)
            anchors.rightMargin: Style.space(6)
            iconText: "󰓶"
            tooltipText: "Detach camera"
            foreground: cameraHero.hasImage ? Qt.rgba(1, 1, 1, 0.92) : root.fg
            fontFamily: root.uiFont
            onClicked: root.detachCamera()
          }
        }

        Item {
          id: chargingBox
          visible: !root.needsLogin && root.showCharging
          width: parent.width
          height: Style.space(96)

          Rectangle {
            anchors.fill: parent
            radius: Math.max(8, Style.cornerRadius)
            color: root.tileFill
            border.width: 1
            border.color: Qt.rgba(root.fg.r, root.fg.g, root.fg.b, 0.10)
          }

          Text {
            textFormat: Text.PlainText
            text: Model.batteryIcon()
            color: root.dim
            font.family: root.uiFont
            font.pixelSize: Style.font.body
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.topMargin: Style.space(10)
            anchors.leftMargin: Style.space(10)
          }

          Row {
            anchors.centerIn: parent
            spacing: 0

            Text {
              id: chargingLabel
              textFormat: Text.PlainText
              text: "Charging"
              color: root.fg
              font.family: root.uiFont
              font.pixelSize: Style.font.title
              font.bold: true
            }

            Text {
              textFormat: Text.PlainText
              text: "."
              color: chargingLabel.color
              font.family: chargingLabel.font.family
              font.pixelSize: chargingLabel.font.pixelSize
              font.bold: chargingLabel.font.bold
              opacity: root.chargingDotStep >= 1 ? 1 : 0
              Behavior on opacity { NumberAnimation { duration: 140 } }
            }
            Text {
              textFormat: Text.PlainText
              text: "."
              color: chargingLabel.color
              font.family: chargingLabel.font.family
              font.pixelSize: chargingLabel.font.pixelSize
              font.bold: chargingLabel.font.bold
              opacity: root.chargingDotStep >= 2 ? 1 : 0
              Behavior on opacity { NumberAnimation { duration: 140 } }
            }
            Text {
              textFormat: Text.PlainText
              text: "."
              color: chargingLabel.color
              font.family: chargingLabel.font.family
              font.pixelSize: chargingLabel.font.pixelSize
              font.bold: chargingLabel.font.bold
              opacity: root.chargingDotStep >= 3 ? 1 : 0
              Behavior on opacity { NumberAnimation { duration: 140 } }
            }
          }
        }

        Grid {
          id: bento
          visible: !root.needsLogin && !root.showCharging
          width: parent.width
          columns: 2
          columnSpacing: Style.space(8)
          rowSpacing: Style.space(8)

          StatBox {
            width: (bento.width - bento.columnSpacing) / 2
            icon: Model.heartIcon()
            value: root.monitoring ? Model.displayNumber(root.vitals.heartRate) : "—"
            unit: "Beats per minute"
            fg: root.fg
            dim: root.dim
            fill: root.tileFill
            fontFamily: root.uiFont
            alert: root.alertFlags.heart
            alertColor: root.alertColor
          }
          StatBox {
            width: (bento.width - bento.columnSpacing) / 2
            icon: Model.airIcon()
            value: root.monitoring && root.vitals.oxygen != null ? Model.displayNumber(root.vitals.oxygen) + "%" : "—"
            unit: "Blood Oxygen"
            fg: root.fg
            dim: root.dim
            fill: root.tileFill
            fontFamily: root.uiFont
            alert: root.alertFlags.oxygen
            alertColor: root.alertColor
          }
          StatBox {
            width: (bento.width - bento.columnSpacing) / 2
            icon: Model.batteryIcon()
            value: root.vitals.battery != null ? String(root.vitals.battery) + "%" : "—"
            unit: "Battery Level"
            fg: root.fg
            dim: root.dim
            fill: root.tileFill
            fontFamily: root.uiFont
            alert: root.alertFlags.battery
            alertColor: root.alertColor
          }
          StatBox {
            width: (bento.width - bento.columnSpacing) / 2
            icon: Model.tempIcon()
            value: root.monitoring ? Model.temperatureText(root.vitals) : "—"
            unit: "Skin Temperature"
            fg: root.fg
            dim: root.dim
            fill: root.tileFill
            fontFamily: root.uiFont
            alert: root.alertFlags.temp
            alertColor: root.alertColor
          }
          StatBox {
            width: (bento.width - bento.columnSpacing) / 2
            icon: Model.moveIcon()
            value: root.monitoring ? Model.movementText(root.vitals) : "—"
            unit: "Movement"
            textValue: true
            fg: root.fg
            dim: root.dim
            fill: root.tileFill
            fontFamily: root.uiFont
            alert: root.alertFlags.movement
            alertColor: root.alertColor
          }
          StatBox {
            width: (bento.width - bento.columnSpacing) / 2
            icon: Model.sleepIcon()
            value: root.monitoring ? (root.vitals.sleepLabel || root.statusTitle) : root.statusTitle
            unit: "Sleep Type"
            textValue: true
            fg: root.fg
            dim: root.dim
            fill: root.tileFill
            fontFamily: root.uiFont
            alert: root.alertFlags.sleep
            alertColor: root.alertColor
          }
        }

        Column {
          visible: root.needsLogin
          width: parent.width
          spacing: Style.space(8)

          Text {
            text: "OWLET SIGN IN"
            color: root.dim
            font.family: root.uiFont
            font.pixelSize: Style.font.caption
            font.letterSpacing: 1
          }

          Text {
            visible: (root.loginError || root.state.error) !== ""
            width: parent.width
            wrapMode: Text.WordWrap
            textFormat: Text.PlainText
            text: root.loginError || root.state.error
            color: root.alertColor
            font.family: root.uiFont
            font.pixelSize: Style.font.bodySmall
          }

          TextField {
            id: emailField
            width: parent.width
            enabled: !root.loginBusy
            placeholderText: "Email"
            text: root.savedEmail
            foreground: root.fg
            font.family: root.uiFont
            onAccepted: if (passwordField) passwordField.forceActiveFocus()
            Keys.onEscapePressed: root.close()
            onVisibleChanged: if (visible && text === "") Qt.callLater(forceActiveFocus)
          }

          Row {
            width: parent.width
            spacing: Style.space(6)

            TextField {
              id: passwordField
              width: parent.width - Style.space(28)
              password: true
              enabled: !root.loginBusy
              placeholderText: root.loginBusy ? "Signing in…" : "Password"
              foreground: root.fg
              font.family: root.uiFont
              onAccepted: root.submitPassword()
              Keys.onEscapePressed: root.close()
              onVisibleChanged: if (visible && emailField && emailField.text !== "") Qt.callLater(forceActiveFocus)
            }

            PanelActionButton {
              iconText: "󰄬"
              tooltipText: "Sign in"
              enabled: !root.loginBusy && passwordField.text.length > 0
              foreground: root.fg
              fontFamily: root.uiFont
              anchors.verticalCenter: parent.verticalCenter
              onClicked: root.submitPassword()
            }
          }
        }

        Column {
          visible: root.alertLines.length > 0
          width: parent.width
          spacing: Style.space(4)

          Repeater {
            model: root.alertLines
            Text {
              required property string modelData
              width: parent.width
              textFormat: Text.PlainText
              text: modelData
              color: root.alertColor
              font.family: root.uiFont
              font.pixelSize: Style.font.body
            }
          }
        }
      }
    }
  }

  PopupCard {
    id: menuPopup
    anchorItem: root.anchorItem
    owner: menuOwner
    bar: root.bar
    open: root.menuOpen && root.anchorItem && root.bar
    padding: Style.space(8)
    contentWidth: menuPopup.fittedContentWidth(Style.space(232))
    contentHeight: menuPopup.fittedContentHeight(menuColumn.implicitHeight)

    Column {
      id: menuColumn
      width: parent.width
      spacing: 0

      Repeater {
        model: root.menuItems

        Item {
          id: menuRow
          required property var modelData
          readonly property string itemId: String(modelData.id || "")
          readonly property string itemLabel: String(modelData.label || "")
          readonly property string kind: String(modelData.kind || "")
          readonly property bool actionable: kind === "action" && modelData.enabled !== false

          width: menuColumn.width
          implicitHeight: kind === "separator" ? Style.space(11) : Style.space(30)

          Rectangle {
            visible: menuRow.kind === "separator"
            anchors.left: parent.left
            anchors.leftMargin: Style.space(10)
            anchors.right: parent.right
            anchors.rightMargin: Style.space(10)
            anchors.verticalCenter: parent.verticalCenter
            height: 1
            color: Color.popups.border
            opacity: 0.45
          }

          Rectangle {
            visible: menuRow.kind !== "separator"
            anchors.fill: parent
            radius: Math.max(2, Style.cornerRadius)
            color: rowMouse.containsMouse && menuRow.actionable
              ? Style.hoverFillFor(root.fg, root.fg)
              : "transparent"
          }

          Text {
            textFormat: Text.PlainText
            visible: menuRow.kind !== "separator"
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin: Style.space(10)
            anchors.right: parent.right
            anchors.rightMargin: Style.space(10)
            text: menuRow.itemLabel
            color: menuRow.kind === "meta" ? root.dim : root.fg
            font.family: root.uiFont
            font.pixelSize: menuRow.kind === "meta" ? Style.font.caption : Style.font.bodySmall
            elide: Text.ElideRight
          }

          MouseArea {
            id: rowMouse
            anchors.fill: parent
            enabled: menuRow.kind !== "separator"
            hoverEnabled: menuRow.actionable
            cursorShape: menuRow.actionable ? Qt.PointingHandCursor : Qt.ArrowCursor
            acceptedButtons: Qt.LeftButton
            onClicked: if (menuRow.actionable) root.chooseMenu(menuRow.itemId)
          }
        }
      }
    }
  }

  FloatingWindow {
    id: cameraWindow
    visible: root.detached
    title: "Omalet Camera"
    color: Color.popups.background
    implicitWidth: Style.space(480)
    implicitHeight: Style.space(300)
    minimumSize: Qt.size(Style.space(280), Style.space(180))

    onVisibleChanged: {
      if (!visible && root.detached) root.detached = false
    }

    Item {
      anchors.fill: parent

      CameraTile {
        anchors.fill: parent
        anchors.margins: Style.space(8)
        icon: Model.cameraIcon()
        caption: root.cameraFloatCaption
        hasImage: !!(root.camera.snapshotPath && root.cameraSnapshotSource !== "")
        imageSource: root.cameraSnapshotSource
        reloadToken: root.camera.fetchedAt || 0
        fg: root.fg
        dim: root.dim
        fill: root.tileFill
        fontFamily: root.uiFont
      }

      Row {
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.topMargin: Style.space(12)
        anchors.rightMargin: Style.space(12)
        spacing: Style.space(4)

        PanelActionButton {
          iconText: "󰏌"
          tooltipText: "Attach"
          foreground: Qt.rgba(1, 1, 1, 0.92)
          fontFamily: root.uiFont
          onClicked: root.attachCamera()
        }

        PanelActionButton {
          iconText: "󰅖"
          tooltipText: "Close"
          foreground: Qt.rgba(1, 1, 1, 0.92)
          fontFamily: root.uiFont
          onClicked: root.detached = false
        }
      }
    }
  }
}
