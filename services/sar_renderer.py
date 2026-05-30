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
        """Create an RGB composite from three specified bands with contrast enhancement."""
        layer = QgsRasterLayer(path, layer_name)
        if not layer.isValid():
            raise RuntimeError("Failed to load SAR image into QGIS.")

        layer.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

        red_idx = BAND_INDEX_MAP.get(band_names[0], 1)
        green_idx = BAND_INDEX_MAP.get(band_names[1], 2)
        blue_idx = BAND_INDEX_MAP.get(band_names[2], 3)

        renderer = QgsMultiBandColorRenderer(
            layer.dataProvider(),
            red_idx,
            green_idx,
            blue_idx,
        )

        # Apply contrast enhancement using cumulative cut (2%-98%)
        try:
            provider = layer.dataProvider()
            canvas = iface.mapCanvas()
            extent = canvas.extent() if canvas else layer.extent()

            if not extent.intersects(layer.extent()):
                extent = layer.extent()

            bands_config = [
                (red_idx, renderer.setRedContrastEnhancement),
                (green_idx, renderer.setGreenContrastEnhancement),
                (blue_idx, renderer.setBlueContrastEnhancement),
            ]

            for band_index, set_enhancement_func in bands_config:
                min_max = provider.cumulativeCut(band_index, 0.02, 0.98, extent, 250000)
                ce = QgsContrastEnhancement(provider.dataType(band_index))
                ce.setContrastEnhancementAlgorithm(QgsContrastEnhancement.StretchToMinimumMaximum)
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
        band_idx = BAND_INDEX_MAP.get(band_name, 1)
        layer = RasterRendererUtils.load_pseudocolor_raster(
            path,
            f"{layer_name} [{band_name}]",
            band_idx=band_idx,
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
            band_idx=1,
            color_ramp_name=color_ramp_name,
            at_top=True,
        )
        if layer is None:
            raise RuntimeError(f"Failed to load SAR composite into QGIS from {path}")
        return layer

    @staticmethod
    def load_sar_to_qgis(path, layer_name, render_mode="RGB: VV, VH, VV/VH Ratio"):
        """Load SAR image with specified render mode.

        Args:
            path: Path to the GeoTIFF file
            layer_name: Name for the layer(s)
            render_mode: One of:
                - "RGB: VV, VH, VV/VH Ratio"
                - "RGB: VV, RVI, DpRVI"
                - "RGB: VV/VH Ratio, RVI, DpRVI"
                - "Band: VV"
                - "Band: VH"
                - "Band: VV/VH Ratio"
                - "Band: RVI"
                - "Band: DpRVI"
        """
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
            # Default to first RGB composite
            return SARRenderer._create_rgb_composite(
                path, layer_name, ["VV", "VH", "VV/VH Ratio"]
            )
