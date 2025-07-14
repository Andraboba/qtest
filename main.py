
import os
import sys
from math import cos, pi, sin, sqrt

from qgis.PyQt.QtCore import (
    QCoreApplication,
    Qt,
    QRectF,
    QVariant,
    QObject,
    pyqtSignal,
    QThread,
)
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsFillSymbol,
    QgsGeometry,
    QgsLayoutExporter,
    QgsLayoutItemLabel,
    QgsLayoutItemMap,
    QgsPointXY,
    QgsPrintLayout,
    QgsProject,
    QgsRectangle,
    QgsSingleSymbolRenderer,
    QgsSymbol,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.gui import (
    QgsMapCanvas,
    QgsMapTool,
    QgsRubberBand,
)


class CircleDrawTool(QgsMapTool):
    """
    Инструмент для рисования окружностей на канвасе QGIS.
    """
    def __init__(self, canvas, layer, main_window):
        super().__init__(canvas)
        self.canvas = canvas
        self.layer = layer
        self.main_window = main_window
        self.rubber_band = None
        self.start_point = None
        self.drawing = False

    def canvasPressEvent(self, event):
        """
        Обрабатывает нажатие мыши для начала рисования окружности.
        """
        if event.button() == Qt.LeftButton:
            self.start_point = self.toMapCoordinates(event.pos())
            self.drawing = True
            self.rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
            self.rubber_band.setColor(Qt.red)
            self.rubber_band.setWidth(2)

    def canvasMoveEvent(self, event):
        """
        Обновляет отображение окружности при движении мыши.
        """
        if self.drawing and self.start_point:
            current_point = self.toMapCoordinates(event.pos())
            self.update_rubber_band(current_point)

    def canvasReleaseEvent(self, event):
        """
        Завершает рисование окружности при отпускании кнопки мыши.
        """
        if event.button() == Qt.LeftButton and self.drawing:
            end_point = self.toMapCoordinates(event.pos())
            self.create_circle(self.start_point, end_point)
            if self.rubber_band:
                self.canvas.scene().removeItem(self.rubber_band)
                self.rubber_band = None
            self.drawing = False
            self.start_point = None

    def update_rubber_band(self, current_point):
        """
        Обновляет временное отображение окружности при рисовании.
        """
        if not self.rubber_band or not self.start_point:
            return
        dx = current_point.x() - self.start_point.x()
        dy = current_point.y() - self.start_point.y()
        radius = sqrt(dx*dx + dy*dy)
        circle_geom = self.create_circle_geometry(self.start_point, radius)
        self.rubber_band.setToGeometry(circle_geom, None)

    def create_circle_geometry(self, center, radius, segments=36):
        """
        Создает геометрию окружности по центру и радиусу.
        """
        points = []
        for i in range(segments + 1):
            angle = 2 * pi * i / segments
            x = center.x() + radius * cos(angle)
            y = center.y() + radius * sin(angle)
            points.append(QgsPointXY(x, y))
        return QgsGeometry.fromPolygonXY([points])

    def create_circle(self, start_point, end_point):
        """
        Добавляет окружность в слой по двум точкам (центр и точка на окружности).
        """
        dx = end_point.x() - start_point.x()
        dy = end_point.y() - start_point.y()
        radius = sqrt(dx*dx + dy*dy)
        if radius < 0.001:
            return
        circle_geom = self.create_circle_geometry(start_point, radius)
        feature = QgsFeature(self.layer.fields())
        feature.setGeometry(circle_geom)
        feature.setAttribute("radius", radius)
        if not self.layer.isEditable():
            self.layer.startEditing()
        result = self.layer.addFeature(feature)
        self.layer.commitChanges()
        if result:
            print(f"Добавлена окружность с радиусом {radius}")
            self.layer.triggerRepaint()
            self.canvas.refresh()
            self.main_window.save_to_shapefile()


class QGISMainWindow(QMainWindow):
    """
    Главное окно приложения QGIS с возможностью рисования окружностей.
    """
    def __init__(self):
        super().__init__()
        self.project = QgsProject.instance()
        self.circle_layer = None
        # Получаем директорию, где находится main.py
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.init_ui()
        self.setup_project()

    def init_ui(self):
        """
        Инициализирует интерфейс пользователя.
        """
        self.setWindowTitle("QGIS Canvas - Circle Drawing")
        self.setGeometry(100, 100, 1200, 800)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        button_layout = QHBoxLayout()
        save_button = QPushButton("Сохранить проект")
        save_button.clicked.connect(self.save_project)
        button_layout.addWidget(save_button)
        export_card_button = QPushButton("Выгрузить карточку")
        export_card_button.clicked.connect(self.export_card)
        button_layout.addWidget(export_card_button)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)
        self.canvas = QgsMapCanvas()
        self.canvas.setCanvasColor(Qt.white)
        self.canvas.enableAntiAliasing(True)
        main_layout.addWidget(self.canvas)

    def setup_project(self):
        """
        Настраивает проект QGIS, слой окружностей и канвас.
        """
        self.create_circle_layer()
        crs = QgsCoordinateReferenceSystem("EPSG:3857")
        self.project.setCrs(crs)
        self.canvas.setDestinationCrs(crs)
        self.project.addMapLayer(self.circle_layer)
        self.canvas.setLayers([self.circle_layer])
        print(f"Слоев на канвасе: {len(self.canvas.layers())}")
        self.circle_tool = CircleDrawTool(self.canvas, self.circle_layer, self)
        self.canvas.setMapTool(self.circle_tool)
        self.canvas.setExtent(QgsRectangle(-20037508, -20037508, 20037508, 20037508))
        self.canvas.zoomByFactor(0.01)
        self.canvas.refresh()

    def create_circle_layer(self):
        """
        Создает временный слой для хранения окружностей.
        """
        self.circle_layer = QgsVectorLayer("Polygon?crs=EPSG:3857", "Circles", "memory")
        if not self.circle_layer.isValid():
            print("Ошибка создания слоя!")
            return
        fields = QgsFields()
        fields.append(QgsField("id", QVariant.Int))
        fields.append(QgsField("radius", QVariant.Double))
        self.circle_layer.dataProvider().addAttributes(fields)
        self.circle_layer.updateFields()
        symbol = QgsFillSymbol.createSimple({
            'color': '0,0,255,80',
            'color_border': 'black',
            'width_border': '0.5',
            'style': 'solid'
        })
        renderer = QgsSingleSymbolRenderer(symbol)
        self.circle_layer.setRenderer(renderer)
        print(f"Слой создан: {self.circle_layer.name()}")
        # Сохраняем shapefile в ту же папку, где main.py
        self.shapefile_path = os.path.abspath(os.path.join(self.base_dir, "circles.shp"))

    def save_to_shapefile(self):
        """
        Сохраняет слой окружностей в shapefile и заменяет memory-слой на файл.
        """
        error = QgsVectorFileWriter.writeAsVectorFormat(
            self.circle_layer,
            self.shapefile_path,
            "UTF-8",
            self.circle_layer.crs(),
            "ESRI Shapefile"
        )
        if error[0] == QgsVectorFileWriter.NoError:
            print("Shapefile сохранен")
            print(f"Shapefile сохранен по пути: {self.shapefile_path}")
            self.replace_memory_layer_with_shapefile()
        else:
            print(f"Ошибка сохранения: {error}")

    def replace_memory_layer_with_shapefile(self):
        """
        Заменяет временный слой на слой из shapefile.
        """
        self.project.removeMapLayer(self.circle_layer.id())
        shapefile_layer = QgsVectorLayer(self.shapefile_path, "Circles", "ogr")
        if shapefile_layer.isValid():
            self.project.addMapLayer(shapefile_layer)
            self.circle_layer = shapefile_layer
            self.circle_tool = CircleDrawTool(self.canvas, self.circle_layer, self)
            self.canvas.setMapTool(self.circle_tool)
            self.canvas.setLayers([self.circle_layer])
            print("Работа продолжается с shapefile-слоем")
        else:
            print("Ошибка загрузки shapefile")

    def save_project(self):
        """
        Сохраняет проект QGIS в файл.
        """
        filename, _ = QFileDialog.getSaveFileName(
            self, "Сохранить проект", "circles_project.qgs", "QGIS Project (*.qgs)"
        )
        if filename:
            if not filename.endswith('.qgs'):
                filename += '.qgs'
            success = self.project.write(filename)
            if success:
                QMessageBox.information(self, "Успех", f"Проект сохранен: {filename}")
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось сохранить проект")

    def export_card(self):
        """
        Запускает экспорт карточки с последней окружностью.
        """
        if self.circle_layer is None:
            QMessageBox.warning(self, "Нет слоя", "Слой окружностей не найден.")
            return
        features = list(self.circle_layer.getFeatures())
        if not features:
            QMessageBox.warning(self, "Нет кругов", "Сначала добавьте круг на карту.")
            return
        circle = features[-1]
        geom = circle.geometry()
        center = geom.centroid().asPoint()
        radius = circle["radius"]
        output_path = os.path.abspath(os.path.join(self.base_dir, "card_export.pdf"))

        # Создаем поток и воркер
        self.export_thread = QThread()
        self.export_worker = CardExportWorker(
            self.project,
            self.circle_layer,
            geom,
            center,
            radius,
            output_path
        )
        self.export_worker.moveToThread(self.export_thread)
        self.export_thread.started.connect(self.export_worker.run)
        self.export_worker.progress.connect(self.on_export_progress)
        self.export_worker.finished.connect(self.on_export_finished)
        self.export_worker.finished.connect(self.export_thread.quit)
        self.export_worker.finished.connect(self.export_worker.deleteLater)
        self.export_thread.finished.connect(self.export_thread.deleteLater)
        self.export_thread.start()

    def on_export_progress(self, value):
        """
        Обрабатывает прогресс экспорта карточки.
        """
        # Можно добавить отображение прогресса (например, через QProgressBar)
        print(f"Прогресс экспорта: {value}%")

    def on_export_finished(self):
        """
        Обрабатывает завершение экспорта карточки.
        """
        # Проверяем PDF в той же папке, где main.py
        output_path = os.path.abspath(os.path.join(self.base_dir, "card_export.pdf"))
        if os.path.exists(output_path):
            QMessageBox.information(self, "Успех", f"Карточка экспортирована: {output_path}")
        else:
            QMessageBox.critical(self, "Ошибка", "Не удалось экспортировать карточку.")


class CardExportWorker(QObject):
    """
    Воркер для экспорта карточки в отдельном потоке.
    """
    progress = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self, project, circle_layer, geom, center, radius, output_path):
        super().__init__()
        self.project = project
        self.circle_layer = circle_layer
        self.geom = geom
        self.center = center
        self.radius = radius
        self.output_path = output_path

    def run(self):
        """
        Выполняет экспорт карточки в PDF.
        """
        try:
            self.progress.emit(10)
            layout = QgsPrintLayout(self.project)
            layout.initializeDefaults()
            layout.setName("CardLayout")
            manager = self.project.layoutManager()
            old_layout = manager.layoutByName("CardLayout")
            if old_layout:
                manager.removeLayout(old_layout)
            manager.addLayout(layout)
            self.progress.emit(30)
            map_item = QgsLayoutItemMap(layout)
            map_item.attemptSetSceneRect(QRectF(10, 10, 120, 120))
            map_item.setFrameEnabled(True)
            map_item.setLayers([self.circle_layer])
            rect = self.geom.boundingBox()
            rect.grow(rect.width() * 0.5)
            map_item.setExtent(rect)
            layout.addLayoutItem(map_item)
            self.progress.emit(60)
            label = QgsLayoutItemLabel(layout)
            label.setText(f"Координаты центра: {self.center.x():.4f}, {self.center.y():.4f}\nРадиус: {self.radius:.2f}")
            label.adjustSizeToText()
            label.attemptSetSceneRect(QRectF(10, 140, 120, 30))
            layout.addLayoutItem(label)
            self.progress.emit(80)
            exporter = QgsLayoutExporter(layout)
            result = exporter.exportToPdf(self.output_path, QgsLayoutExporter.PdfExportSettings())
            self.progress.emit(100)
        finally:
            self.finished.emit()


def main():
    """
    Точка входа в приложение.
    """
    app = QgsApplication([], True)
    app.initQgis()
    qt_app = QApplication(sys.argv)
    try:
        window = QGISMainWindow()
        window.show()
        sys.exit(qt_app.exec_())
    finally:
        app.exitQgis()


if __name__ == "__main__":
    main()