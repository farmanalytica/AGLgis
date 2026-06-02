from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsContrastEnhancement,
    QgsLayerTreeLayer,
    QgsMultiBandColorRenderer,
    QgsProject,
    QgsRasterLayer,
)
from qgis.utils import iface

from .raster_renderer_utils import RasterRendererUtils


BAND_INDEX_MAP = {
    "VV": 1,
    "VH": 2,
    "VV/VH Ratio": 3,
    "RVI": 4,
    "DpRVI": 5,
}


class SARRenderer:
    @staticmethod
    def _create_rgb_composite(path, layer_name, band_names):

        layer = QgsRasterLayer(path, layer_name)
        if not layer.isValid():
            raise RuntimeError("Failed to load SAR image into QGIS.")

        layer.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

        red_index = BAND_INDEX_MAP.get(band_names[0], 1)
        green_index = BAND_INDEX_MAP.get(band_names[1], 2)
        blue_index = BAND_INDEX_MAP.get(band_names[2], 3)

        renderer = QgsMultiBandColorRenderer(
            layer.dataProvider(),
            red_index,
            green_index,
            blue_index,
        )

        try:
            provider = layer.dataProvider()
            canvas = iface.mapCanvas()
            extent = canvas.extent() if canvas else layer.extent()

            if not extent.intersects(layer.extent()):
                extent = layer.extent()

            bands_config = [
                (red_index, renderer.setRedContrastEnhancement),
                (green_index, renderer.setGreenContrastEnhancement),
                (blue_index, renderer.setBlueContrastEnhancement),
            ]

            for band_index, set_enhancement_func in bands_config:
                min_max = provider.cumulativeCut(band_index, 0.02, 0.98, extent, 250000)
                ce = QgsContrastEnhancement(provider.dataType(band_index))
                ce.setContrastEnhancementAlgorithm(
                    QgsContrastEnhancement.StretchToMinimumMaximum
                )
                ce.setMinimumValue(min_max[0])
                ce.setMaximumValue(min_max[1])
                set_enhancement_func(ce)
        except Exception as e:
            print(f"Error applying contrast enhancement: {e}")

        layer.setRenderer(renderer)
        QgsProject.instance().addMapLayer(layer, False)
        root = QgsProject.instance().layerTreeRoot()
        root.insertChildNode(0, QgsLayerTreeLayer(layer))
        layer.triggerRepaint()

        return layer

    @staticmethod
    def _create_single_band_layer(path, layer_name, band_name):
        """Create a single-band pseudocolor layer with Viridis palette."""
        band_index = BAND_INDEX_MAP.get(band_name, 1)
        layer = RasterRendererUtils.load_pseudocolor_raster(
            path,
            f"{layer_name} [{band_name}]",
            band_index=band_index,
            color_ramp_name="Viridis",
            at_top=True,
        )

        if layer is None:
            raise RuntimeError(f"Failed to load SAR image into QGIS from {path}")

        return layer

    @staticmethod
    def load_composite_to_qgis(path, layer_name, color_ramp_name="Viridis"):
        """Load a single-band composite GeoTIFF with a pseudocolor palette."""
        layer = RasterRendererUtils.load_pseudocolor_raster(
            path,
            layer_name,
            band_index=1,
            color_ramp_name=color_ramp_name,
            at_top=True,
        )
        if layer is None:
            raise RuntimeError(f"Failed to load SAR composite into QGIS from {path}")
        return layer

    @staticmethod
    def load_sar_to_qgis(path, layer_name, render_mode="RGB: VV, VH, VV/VH Ratio"):

        if render_mode == "RGB: VV, VH, VV/VH Ratio":
            return SARRenderer._create_rgb_composite(
                path, layer_name, ["VV", "VH", "VV/VH Ratio"]
            )
        elif render_mode == "RGB: VV, RVI, DpRVI":
            return SARRenderer._create_rgb_composite(
                path, layer_name, ["VV", "RVI", "DpRVI"]
            )
        elif render_mode == "RGB: VV/VH Ratio, RVI, DpRVI":
            return SARRenderer._create_rgb_composite(
                path, layer_name, ["VV/VH Ratio", "RVI", "DpRVI"]
            )
        elif render_mode.startswith("Band: "):
            band_name = render_mode.replace("Band: ", "")
            return SARRenderer._create_single_band_layer(path, layer_name, band_name)
        else:
            return SARRenderer._create_rgb_composite(
                path, layer_name, ["VV", "VH", "VV/VH Ratio"]
            )
