# -*- coding: utf-8 -*-
"""
Common raster rendering utilities for pseudocolor visualization.

Provides reusable methods for applying pseudocolor renderers with color ramps
to raster layers, following QGIS 3.44+ patterns.
"""

from qgis.core import (
    QgsColorRampShader,
    QgsLayerTreeLayer,
    QgsProject,
    QgsRasterShader,
    QgsSingleBandPseudoColorRenderer,
    QgsStyle,
)


class RasterRendererUtils:
    """Common utilities for raster rendering with color ramps."""

    @staticmethod
    def apply_pseudocolor_renderer(
        raster_layer,
        band_idx,
        color_ramp_name,
        min_val,
        max_val,
        num_stops=256,
    ):
        """Apply pseudocolor rendering to a raster layer.

        Args:
            raster_layer: QgsRasterLayer to render
            band_idx: Band index to render (1-based)
            color_ramp_name: Name of QGIS style color ramp (e.g., "Viridis", "Magma")
            min_val: Minimum value for color ramp
            max_val: Maximum value for color ramp
            num_stops: Number of color stops (default 256)

        Returns:
            True if successful, False if color ramp not found
        """
        # Load the color ramp from QGIS style manager
        style = QgsStyle.defaultStyle()
        color_ramp = style.colorRamp(color_ramp_name)

        if not color_ramp:
            return False

        # Handle edge case where min == max
        if min_val == max_val:
            max_val = min_val + 1.0

        # Create a color ramp shader with interpolated classification
        color_ramp_shader = QgsColorRampShader()
        color_ramp_shader.setColorRampType(QgsColorRampShader.Interpolated)

        # Create color ramp items using the actual data range
        color_ramp_items = []
        for i in range(num_stops):
            value = min_val + (max_val - min_val) * (i / (num_stops - 1))
            color = color_ramp.color(i / (num_stops - 1))
            color_ramp_items.append(QgsColorRampShader.ColorRampItem(value, color))

        # Set the color ramp items
        color_ramp_shader.setColorRampItemList(color_ramp_items)

        # Create a raster shader
        raster_shader = QgsRasterShader()
        raster_shader.setRasterShaderFunction(color_ramp_shader)

        # Create and apply the renderer
        renderer = QgsSingleBandPseudoColorRenderer(
            raster_layer.dataProvider(),
            band_idx,
            raster_shader,
        )

        # Set the classification range
        renderer.setClassificationMin(min_val)
        renderer.setClassificationMax(max_val)

        raster_layer.setRenderer(renderer)

        return True

    @staticmethod
    def add_layer_to_project(raster_layer, at_top=True):
        """Add a raster layer to the project at top or bottom of Layers panel.

        Args:
            raster_layer: QgsRasterLayer to add
            at_top: If True, add to top; if False, add to bottom (default True)
        """
        QgsProject.instance().addMapLayer(raster_layer, False)

        root = QgsProject.instance().layerTreeRoot()
        if at_top:
            root.insertChildNode(0, QgsLayerTreeLayer(raster_layer))
        else:
            root.insertLayer(-1, raster_layer)

    @staticmethod
    def load_pseudocolor_raster(
        path,
        layer_name,
        band_idx,
        color_ramp_name,
        at_top=True,
    ):
        """Load and apply pseudocolor rendering to a raster in one call.

        Args:
            path: Path to raster file
            layer_name: Name for the layer in QGIS
            band_idx: Band index to render (1-based)
            color_ramp_name: Name of QGIS style color ramp
            at_top: If True, add layer at top of panel (default True)

        Returns:
            The styled QgsRasterLayer, or None if failed
        """
        from qgis.core import QgsRasterLayer

        layer = QgsRasterLayer(path, layer_name)
        if not layer.isValid():
            return None

        # Get actual data range from the band
        provider = layer.dataProvider()
        stats = provider.bandStatistics(band_idx)
        min_val = stats.minimumValue
        max_val = stats.maximumValue

        # Apply pseudocolor rendering
        success = RasterRendererUtils.apply_pseudocolor_renderer(
            layer, band_idx, color_ramp_name, min_val, max_val
        )

        if not success:
            return None

        # Add to project
        RasterRendererUtils.add_layer_to_project(layer, at_top=at_top)
        layer.triggerRepaint()

        return layer
