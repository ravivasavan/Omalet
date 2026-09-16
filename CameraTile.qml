import QtQuick
import qs.Commons

Item {
  id: root

  property string imageSource: ""
  property int reloadToken: 0
  property string caption: ""
  property string icon: ""
  property bool hasImage: false
  property color fg: Color.popups.text
  property color dim: Qt.darker(Color.popups.text, 1.3)
  property color fill: "transparent"
  property string fontFamily: Style.font.family

  implicitWidth: Style.space(320)
  implicitHeight: Math.max(Style.space(96), Math.round(width * 9 / 16))

  Rectangle {
    anchors.fill: parent
    radius: Math.max(8, Style.cornerRadius)
    color: root.fill
    border.width: 1
    border.color: Qt.rgba(root.fg.r, root.fg.g, root.fg.b, 0.10)
    clip: true

    Image {
      id: frame
      visible: root.hasImage && root.imageSource !== ""
      anchors.fill: parent
      fillMode: Image.PreserveAspectCrop
      asynchronous: true
      cache: false
    }

    Text {
      visible: !root.hasImage
      textFormat: Text.PlainText
      text: root.icon
      color: root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.body
      anchors.top: parent.top
      anchors.left: parent.left
      anchors.topMargin: Style.space(10)
      anchors.leftMargin: Style.space(10)
    }

    Rectangle {
      visible: root.hasImage
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.bottom: parent.bottom
      height: Style.space(40)
      gradient: Gradient {
        GradientStop { position: 0.0; color: "transparent" }
        GradientStop { position: 1.0; color: Qt.rgba(0, 0, 0, 0.45) }
      }
    }

    Text {
      visible: root.caption !== ""
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.bottom: parent.bottom
      anchors.leftMargin: Style.space(10)
      anchors.rightMargin: Style.space(10)
      anchors.bottomMargin: Style.space(10)
      textFormat: Text.PlainText
      text: root.caption
      color: root.hasImage ? Qt.rgba(1, 1, 1, 0.92) : root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
      elide: Text.ElideRight
    }
  }

  function loadFrame() {
    frame.source = ""
    if (root.hasImage && root.imageSource !== "") frame.source = root.imageSource
  }

  onHasImageChanged: loadFrame()
  onImageSourceChanged: loadFrame()
  onReloadTokenChanged: loadFrame()
  Component.onCompleted: loadFrame()
}
