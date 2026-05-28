# -*- coding: utf-8 -*-
"""
DEM rendering and styling module.

Handles DEM layer loading and rendering with Magma color scheme.
"""

from qgis.core import QgsRasterLayer

from .raster_renderer_utils import RasterRendererUtils


class DEMRenderer:
    """Handles DEM rendering and layer styling with color ramps."""

    @staticmethod
    def load_dem_to_qgis(path: str, dataset_name: str) -> QgsRasterLayer:
        """
        Load a DEM GeoTIFF into QGIS with a Magma color ramp renderer.

        Args:
            path: Absolute path to the GeoTIFF file.
            dataset_name: Name used as the layer label in QGIS.

        Returns:
            The loaded and styled QgsRasterLayer.

        Raises:
            RuntimeError: If the raster layer is invalid.
        """
        raster_layer = RasterRendererUtils.load_pseudocolor_raster(
            path, dataset_name, band_idx=1, color_ramp_name="Magma", at_top=True
        )

        if raster_layer is None:
            raise RuntimeError("Failed to load DEM into QGIS.")

        return raster_layer
