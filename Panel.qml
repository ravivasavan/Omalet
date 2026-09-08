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
  readonly property string pluginDir: Quickshell.env("HOME") + "/.config/omarchy/plugins/ravivasavan.owlet"
  readonly property string statePath: Quickshell.env("HOME") + "/.local/state/omarchy/owlet.json"
  readonly property string authPath: Quickshell.env("HOME") + "/.local/state/omarchy/owlet-auth.json"
  property string savedEmail: ""

  readonly property color tileFill: Style.normalFillFor(root.fg, Color.accent)
  readonly property bool monitoring: state.status === "monitoring"
  readonly property var alertFlags: Model.alertTiles(state)
  readonly property bool showCharging: Model.showChargingPanel(state)
  property bool loginBusy: false
  property string loginError: ""
  property int chargingDotStep: 0

  function open() {
    openedFromHotkey = false
    root.controller.show()
    stateFile.reload()
    root.refresh()
  }

  function openFromHotkey() {
    openedFromHotkey = true
    root.open()
  }

  function close() {
    root.controller.hide()
  }

  function toggle() {
    if (root.opened) root.close()
    else root.open()
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
  }

  function signIn() {
    if (!root.opened) root.open()
    Qt.callLater(function() {
      if (emailField && String(emailField.text || "") === "") emailField.forceActiveFocus()
      else if (passwordField) passwordField.forceActiveFocus()
    })
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

  Process {
    id: fetchProc
    command: [root.pluginDir + "/fetch.sh"]
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

  IpcHandler {
    target: root.ipcTarget

    function open(): void { root.openFromHotkey() }
    function close(): void { root.close() }
    function show(): void { root.openFromHotkey() }
    function hide(): void { root.close() }
    function toggle(): void { root.toggle() }
    function refresh(): void { root.refresh() }
    function login(): void { root.signIn() }
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
}
