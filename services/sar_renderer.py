from qgis.core import (
    QgsRasterLayer,
    QgsMultiBandColorRenderer,
)

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
        """Create an RGB composite from three specified bands."""
        layer = QgsRasterLayer(path, layer_name)
        if not layer.isValid():
            raise RuntimeError("Failed to load SAR image into QGIS.")

        red_idx = BAND_INDEX_MAP.get(band_names[0], 1)
        green_idx = BAND_INDEX_MAP.get(band_names[1], 2)
        blue_idx = BAND_INDEX_MAP.get(band_names[2], 3)

        renderer = QgsMultiBandColorRenderer(
            layer.dataProvider(),
            red_idx,
            green_idx,
            blue_idx,
        )
        layer.setRenderer(renderer)
        layer.renderer().setAlphaBand(0)

        RasterRendererUtils.add_layer_to_project(layer, at_top=True)
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
