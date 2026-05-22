from qgis.core import QgsLayerTreeLayer, QgsProject, QgsRasterLayer


class SARRenderer:
    @staticmethod
    def load_sar_to_qgis(path, layer_name):
        raster_layer = QgsRasterLayer(path, layer_name)
        if not raster_layer.isValid():
            raise RuntimeError("Failed to load SAR image into QGIS.")

        QgsProject.instance().addMapLayer(raster_layer, False)
        QgsProject.instance().layerTreeRoot().insertChildNode(
            0, QgsLayerTreeLayer(raster_layer)
        )
        raster_layer.triggerRepaint()

        return raster_layer
