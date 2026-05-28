from qgis.core import (
    QgsLayerTreeLayer,
    QgsProject,
    QgsRasterLayer,
    QgsMultiBandColorRenderer,
    QgsContrastEnhancement,
    QgsRasterDataProvider,
    QgsSingleBandPseudoColorRenderer,
    QgsRasterShader,
    QgsColorRampShader,
    QgsStyle,
)


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

        QgsProject.instance().addMapLayer(layer, False)
        QgsProject.instance().layerTreeRoot().insertChildNode(
            0, QgsLayerTreeLayer(layer)
        )
        layer.triggerRepaint()

        return layer

    @staticmethod
    def _create_single_band_layer(path, layer_name, band_name):
        """Create a single-band pseudocolor layer with Viridis palette."""
        band_layer = QgsRasterLayer(path, f"{layer_name} [{band_name}]")
        if not band_layer.isValid():
            raise RuntimeError(f"Failed to load SAR image into QGIS from {path}")

        band_idx = BAND_INDEX_MAP.get(band_name, 1)

        # Add layer to project first
        QgsProject.instance().addMapLayer(band_layer, False)
        QgsProject.instance().layerTreeRoot().insertChildNode(
            0, QgsLayerTreeLayer(band_layer)
        )

        # Create a color ramp shader
        color_ramp_shader = QgsColorRampShader()
        color_ramp_shader.setColorRampType(QgsColorRampShader.Interpolated)

        # Load the Viridis color ramp from QGIS style manager
        style = QgsStyle.defaultStyle()
        color_ramp = style.colorRamp("Viridis")

        if color_ramp:
            # Define the number of color stops
            num_stops = 256
            min_val = 0.0
            max_val = 1.0

            # Create color ramp items using the actual data range
            color_ramp_items = []
            for i in range(num_stops):
                value = min_val + (max_val - min_val) * (i / (num_stops - 1))
                color = color_ramp.color(i / (num_stops - 1))
                color_ramp_items.append(QgsColorRampShader.ColorRampItem(value, color))

            # Set the color ramp items to the color ramp shader
            color_ramp_shader.setColorRampItemList(color_ramp_items)

            # Create a raster shader
            raster_shader = QgsRasterShader()
            raster_shader.setRasterShaderFunction(color_ramp_shader)

            # Apply the raster shader to the renderer
            renderer = QgsSingleBandPseudoColorRenderer(
                band_layer.dataProvider(),
                band_idx,
                raster_shader
            )

            # Set the classification range
            renderer.setClassificationMin(min_val)
            renderer.setClassificationMax(max_val)

            band_layer.setRenderer(renderer)

        # Refresh the layer
        band_layer.triggerRepaint()

        return band_layer

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
