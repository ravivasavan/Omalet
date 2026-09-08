import QtQuick
import qs.Commons

Item {
  id: root

  property string icon: ""
  property string value: "—"
  property string unit: ""
  property bool textValue: false
  property bool alert: false
  property color fg: Color.popups.text
  property color dim: Qt.darker(Color.popups.text, 1.3)
  property color fill: "transparent"
  property color alertColor: Color.urgent
  property string fontFamily: Style.font.family

  implicitWidth: Style.space(148)
  implicitHeight: Style.space(96)

  Rectangle {
    anchors.fill: parent
    radius: Math.max(8, Style.cornerRadius)
    color: root.fill
    border.width: 1
    border.color: Qt.rgba(root.fg.r, root.fg.g, root.fg.b, 0.10)
  }

  Rectangle {
    id: flash
    anchors.fill: parent
    radius: Math.max(8, Style.cornerRadius)
    color: root.alertColor
    opacity: 0
  }

  SequentialAnimation {
    id: flashAnim
    running: root.alert
    loops: Animation.Infinite
    NumberAnimation {
      target: flash
      property: "opacity"
      from: 0.06
      to: 0.20
      duration: 900
      easing.type: Easing.InOutSine
    }
    NumberAnimation {
      target: flash
      property: "opacity"
      from: 0.20
      to: 0.06
      duration: 900
      easing.type: Easing.InOutSine
    }
  }

  onAlertChanged: if (!root.alert) flash.opacity = 0

  Text {
    textFormat: Text.PlainText
    text: root.icon
    color: root.alert ? root.alertColor : root.dim
    font.family: root.fontFamily
    font.pixelSize: Style.font.body
    anchors.top: parent.top
    anchors.left: parent.left
    anchors.topMargin: Style.space(10)
    anchors.leftMargin: Style.space(10)
  }

  Column {
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    anchors.leftMargin: Style.space(10)
    anchors.rightMargin: Style.space(10)
    anchors.bottomMargin: Style.space(10)
    spacing: Style.space(2)

    Text {
      width: parent.width
      textFormat: Text.PlainText
      text: root.value
      color: root.alert ? root.alertColor : root.fg
      font.family: root.fontFamily
      font.pixelSize: root.textValue ? Style.font.title : Style.font.display
      font.bold: true
      elide: Text.ElideRight
    }

    Text {
      visible: root.unit !== ""
      width: parent.width
      textFormat: Text.PlainText
      text: root.unit
      color: root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
      wrapMode: Text.WordWrap
    }
  }
}
