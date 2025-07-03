
import sys
from math import sqrt, pi, sin, cos
import os

from qgis.PyQt.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QFileDialog, QMessageBox
from qgis.PyQt.QtCore import Qt

from qgis.core import (QgsApplication, QgsProject, QgsVectorLayer, 
                      QgsFeature, QgsGeometry, QgsPointXY, QgsWkbTypes,
                      QgsCoordinateReferenceSystem, QgsField, QgsFields, QgsRectangle,
                      QgsSymbol, QgsSingleSymbolRenderer, QgsFillSymbol, QgsVectorFileWriter)
from qgis.gui import QgsMapCanvas, QgsMapTool, QgsRubberBand
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor


class CircleDrawTool(QgsMapTool):
    
    def __init__(self, canvas, layer, main_window):
        super().__init__(canvas)
        self.canvas = canvas
        self.layer = layer
        self.main_window = main_window
        self.rubber_band = None
        self.start_point = None
        self.drawing = False
        
    def canvasPressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_point = self.toMapCoordinates(event.pos())
            self.drawing = True
            
            self.rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
            self.rubber_band.setColor(Qt.red)
            self.rubber_band.setWidth(2)
            
    def canvasMoveEvent(self, event):
        if self.drawing and self.start_point:
            current_point = self.toMapCoordinates(event.pos())
            self.update_rubber_band(current_point)
            
    def canvasReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.drawing:
            end_point = self.toMapCoordinates(event.pos())
            self.create_circle(self.start_point, end_point)
            
            if self.rubber_band:
                self.canvas.scene().removeItem(self.rubber_band)
                self.rubber_band = None
                
            self.drawing = False
            self.start_point = None
            
    def update_rubber_band(self, current_point):
        if not self.rubber_band or not self.start_point:
            return
            
        dx = current_point.x() - self.start_point.x()
        dy = current_point.y() - self.start_point.y()
        radius = sqrt(dx*dx + dy*dy)
        
        circle_geom = self.create_circle_geometry(self.start_point, radius)
        self.rubber_band.setToGeometry(circle_geom, None)
        
    def create_circle_geometry(self, center, radius, segments=36):
        points = []
        for i in range(segments + 1):
            angle = 2 * pi * i / segments
            x = center.x() + radius * cos(angle)
            y = center.y() + radius * sin(angle)
            points.append(QgsPointXY(x, y))
            
        return QgsGeometry.fromPolygonXY([points])
        
    def create_circle(self, start_point, end_point):
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
    
    def __init__(self):
        super().__init__()
        self.project = QgsProject.instance()
        self.circle_layer = None
        self.init_ui()
        self.setup_project()
        
    def init_ui(self):
        self.setWindowTitle("QGIS Canvas - Circle Drawing")
        self.setGeometry(100, 100, 1200, 800)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        
        button_layout = QHBoxLayout()
        save_button = QPushButton("Сохранить проект")
        save_button.clicked.connect(self.save_project)
        button_layout.addWidget(save_button)
        button_layout.addStretch()
        
        main_layout.addLayout(button_layout)
        
        self.canvas = QgsMapCanvas()
        self.canvas.setCanvasColor(Qt.white)
        self.canvas.enableAntiAliasing(True)
        
        main_layout.addWidget(self.canvas)
        
    def setup_project(self):
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
        
        # Явно сохраняем shapefile в C:\te
        self.shapefile_path = os.path.abspath(os.path.join("C:\\te", "circles.shp"))
        
    def save_to_shapefile(self):
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
        # Удаляем memory-слой из проекта
        self.project.removeMapLayer(self.circle_layer.id())
        # Загружаем слой из shapefile
        shapefile_layer = QgsVectorLayer(self.shapefile_path, "Circles", "ogr")
        if shapefile_layer.isValid():
            self.project.addMapLayer(shapefile_layer)
            self.circle_layer = shapefile_layer
            # Переназначаем инструмент рисования на новый слой
            self.circle_tool = CircleDrawTool(self.canvas, self.circle_layer, self)
            self.canvas.setMapTool(self.circle_tool)
            self.canvas.setLayers([self.circle_layer])
            print("Работа продолжается с shapefile-слоем")
        else:
            print("Ошибка загрузки shapefile")
        
    def save_project(self):
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


def main():
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