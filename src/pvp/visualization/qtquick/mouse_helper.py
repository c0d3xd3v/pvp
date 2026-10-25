from PySide6.QtCore import Qt, QEvent, QPointF
from PySide6.QtGui import QMouseEvent, QWheelEvent, QHoverEvent


def cloneMouseEvent(event: QMouseEvent):
    return QMouseEvent(
        event.type(),
        event.position(),
        event.scenePosition(),
        event.globalPosition(),
        event.button(),
        event.buttons(),
        event.modifiers(),
        event.source(),
    )

def create_mouse_event_from_hover_event(hover_event: QHoverEvent) -> QMouseEvent:
    # Extract relevant information from the hover event
    pos = hover_event.pos()
    global_pos = hover_event.scenePosition()  # Global position
    button_state = Qt.NoButton  # Since it's a hover event, no button is pressed
    modifiers = hover_event.modifiers()
    buttons = Qt.MouseButton()

    # Create a QMouseEvent with the extracted information
    mouse_event = QMouseEvent(
        QEvent.MouseMove,
        pos,
        global_pos,
        button_state,
        buttons,
        modifiers
    )

    return mouse_event

def cloneWheelEvent(event: QWheelEvent):
    return QWheelEvent(
        event.position(),
        event.globalPosition(),
        event.pixelDelta(),
        event.angleDelta(),
        event.buttons(),
        event.modifiers(),
        event.phase(),
        event.inverted(),
        event.source(),
    )

def convertToMouseEvent(
    eventType: QEvent.Type,
    localPos: QPointF,
    button: Qt.MouseButton,
    buttons: Qt.MouseButtons,
    modifiers: Qt.KeyboardModifiers,
):
    return QMouseEvent(eventType, localPos, button, buttons, modifiers)
