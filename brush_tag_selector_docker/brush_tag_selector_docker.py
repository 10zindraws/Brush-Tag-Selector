import os
from krita import Krita, DockWidget, DockWidgetFactory, DockWidgetFactoryBase
from PyQt5.QtWidgets import (
    QPushButton, QVBoxLayout, QWidget, QComboBox,
    QLayout, QSizePolicy, QButtonGroup, QAbstractButton
)
from PyQt5.QtCore import QSize, QPoint, QRect, Qt

DOCKER_TITLE = 'Brush Tag Selector'
DOCKER_ID = 'brush_tag_selector_docker'
TAGS_FILENAME = "tags.txt"

# ---------------- FlowLayout (unchanged) ----------------
class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []

    def addItem(self, item): self.itemList.append(item)
    def count(self): return len(self.itemList)
    def itemAt(self, i): return self.itemList[i] if 0 <= i < len(self.itemList) else None
    def takeAt(self, i): return self.itemList.pop(i) if 0 <= i < len(self.itemList) else None
    def expandingDirections(self): return Qt.Orientations(0)
    def hasHeightForWidth(self): return True

    def heightForWidth(self, width):
        return self._doLayout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._doLayout(rect, False)

    def sizeHint(self): return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        return size

    def _doLayout(self, rect, testOnly):
        x, y, lineHeight = rect.x(), rect.y(), 0
        for item in self.itemList:
            w = item.sizeHint().width()
            h = item.sizeHint().height()
            if x + w > rect.right() and lineHeight:
                x = rect.x()
                y += lineHeight
                lineHeight = 0
            if not testOnly:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x += w
            lineHeight = max(lineHeight, h)
        return y + lineHeight - rect.y()

# ---------------- Docker ----------------
class BrushTagSelectorDocker(DockWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(DOCKER_TITLE)
        self.krita = Krita.instance()
        self.plugin_dir = os.path.dirname(os.path.abspath(__file__))
        self.tags_file = os.path.join(self.plugin_dir, TAGS_FILENAME)

        self.main = QWidget(self)
        self.setWidget(self.main)

        self.layout = QVBoxLayout(self.main)
        self.flow = FlowLayout(spacing=3)
        self.layout.addLayout(self.flow)
        self.layout.addStretch(1)

        self.buttons = []
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)

        self._combo = None
        self._changing = False

        self.group.buttonClicked.connect(self._on_button_clicked)

        # Wait until Krita UI is initialized
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(1000, self._initialize)

    # ---------------- Initialization ----------------
    def _initialize(self):
        self._combo = self._find_preset_combo()
        if not self._combo:
            print(f"{DOCKER_TITLE}: Could not find Preset Docker ComboBox")
            return

        # Listen to ComboBox model for tag changes
        model = self._combo.model()
        model.rowsInserted.connect(self._on_tags_changed)
        model.rowsRemoved.connect(self._on_tags_changed)
        model.modelReset.connect(self._on_tags_changed)

        # Listen to selection changes
        self._combo.currentIndexChanged[str].connect(self._on_combo_changed)

        # Initial sync
        self._sync_tags_from_krita()
        self._rebuild_buttons()

    # ---------------- Tag sync ----------------
    def _sync_tags_from_krita(self):
        if not self._combo:
            return

        tags = [self._combo.itemText(i) for i in range(self._combo.count())]

        try:
            with open(self.tags_file, "w", encoding="utf-8") as f:
                for t in tags:
                    f.write(t + "\n")
        except Exception as e:
            print(f"{DOCKER_TITLE}: Error writing tags.txt: {e}")

    def _on_tags_changed(self, *args):
        self._sync_tags_from_krita()
        self._rebuild_buttons()

    # ---------------- UI rebuild ----------------
    def _rebuild_buttons(self):
        for b in self.buttons:
            self.flow.removeWidget(b)
            b.deleteLater()
        self.buttons.clear()

        if not os.path.exists(self.tags_file):
            return

        try:
            with open(self.tags_file, "r", encoding="utf-8") as f:
                tags = [l.strip() for l in f if l.strip()]
        except Exception as e:
            print(f"{DOCKER_TITLE}: Error reading tags.txt: {e}")
            return

        for tag in tags:
            btn = QPushButton(tag)
            btn.setCheckable(True)
            self.group.addButton(btn)
            self.flow.addWidget(btn)
            self.buttons.append(btn)

        if self._combo:
            self._sync_button_state(self._combo.currentText())

    # ---------------- Button ↔ ComboBox sync ----------------
    def _on_button_clicked(self, btn):
        if not self._combo:
            return
        for i in range(self._combo.count()):
            if self._combo.itemText(i) == btn.text():
                self._changing = True
                self._combo.setCurrentIndex(i)
                self._changing = False
                break

    def _on_combo_changed(self, text):
        if self._changing:
            return
        self._sync_button_state(text)

    def _sync_button_state(self, text):
        for b in self.buttons:
            b.setChecked(b.text() == text)

    # ---------------- Krita helpers ----------------
    def _find_preset_combo(self):
        dock = next((d for d in self.krita.dockers() if d.objectName() == "PresetDocker"), None)
        if dock:
            combo = dock.findChild(QComboBox)
            if combo:
                return combo
        return None

    def canvasChanged(self, canvas): pass

# ---------------- Registration ----------------
krita_instance_global = Krita.instance()
if krita_instance_global:
    dock_widget_factory = DockWidgetFactory(
        DOCKER_ID,
        DockWidgetFactoryBase.DockRight,
        BrushTagSelectorDocker
    )
    krita_instance_global.addDockWidgetFactory(dock_widget_factory)
else:
    print(f"Could not register {DOCKER_TITLE}: Krita instance not available.")
