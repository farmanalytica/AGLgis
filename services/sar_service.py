import os
import tempfile

import ee
import requests
from ee_s1_ard import S1ARDImageCollection
from datetime import datetime, timedelta

try:
    from osgeo import gdal
except ImportError:
    gdal = None


class SARService:
    PLOTLY_SEQUENTIAL_PALETTE = [
        "#0d0887",
        "#46039f",
        "#7201a8",
        "#9c179e",
        "#bd3786",
        "#d8576b",
        "#ed7953",
        "#fb9f3a",
        "#fdca26",
        "#f0f921",
    ]

    INDEX_REGISTRY = {
        "VV/VH Ratio": {
            "band": "VVVH_ratio",
            "add_fn": "add_vvvh_ratio_band",
            "title": "VV/VH Ratio Mean Time Series",
            "ylabel": "VV/VH Ratio Mean",
            "band_label": "VV/VH Ratio",
        },
        "RVI": {
            "band": "RVI",
            "add_fn": "add_rvi_band",
            "title": "Radar Vegetation Index (RVI) Time Series",
            "ylabel": "RVI Mean",
            "band_label": "RVI",
        },
        "DpRVI": {
            "band": "DpRVI",
            "add_fn": "add_dprvi_band",
            "title": "Dual-pol Vegetation Index (DpRVI) Time Series",
            "ylabel": "DpRVI Mean",
            "band_label": "DpRVI",
        },
    }

    @staticmethod
    def get_collection(
        aoi,
        start_date,
        end_date,
        polarization,
        output_format,
        apply_border_noise_correction,
        apply_terrain_flattening,
        apply_speckle_filtering,
        ascending=False,
    ):
        processor = S1ARDImageCollection(
            geometry=aoi,
            start_date=start_date,
            stop_date=end_date,
            polarization=polarization,
            apply_border_noise_correction=apply_border_noise_correction,
            apply_terrain_flattening=apply_terrain_flattening,
            apply_speckle_filtering=apply_speckle_filtering,
            output_format=output_format,
            ascending=ascending,
        )

        return processor.get_collection().sort("system:time_start", False)

    @staticmethod
    def add_vvvh_ratio_band(image):
        ratio = image.select("VV").divide(image.select("VH")).rename("VVVH_ratio")
        return image.addBands(ratio)

    @staticmethod
    def add_rvi_band(image):
        rvi = image.select("VH").multiply(4).divide(
            image.select("VV").add(image.select("VH"))
        ).rename("RVI")
        return image.addBands(rvi)

    @staticmethod
    def add_dprvi_band(image):
        dprvi = image.select("VH").divide(
            image.select("VH").add(image.select("VV"))
        ).rename("DpRVI")
        return image.addBands(dprvi)

    @staticmethod
    def get_index_timeseries(collection, aoi, band_name):
        def get_mean(image):
            stats = image.select(band_name).reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=aoi,
                scale=10,
                maxPixels=1e9,
            )

            date = image.date().format("YYYY-MM-dd")

            return ee.Feature(
                None,
                {
                    "date": date,
                    f"{band_name}_mean": stats.get(band_name),
                },
            )

        result = collection.map(get_mean).getInfo()

        data = []
        for feature in result["features"]:
            properties = feature.get("properties", {})
            value = properties.get(f"{band_name}_mean")
            # reduceRegion returns null when an acquisition has no unmasked
            # pixels over the AOI (e.g. a swath that only clips the AOI edge).
            # Drop those dates at the source so the plot, CSV export, and batch
            # download all work from the same valid-only series.
            if value is None:
                continue
            data.append(
                {
                    "dates": properties.get("date"),
                    "AOI_average": value,
                }
            )

        return data

    @staticmethod
    def get_vvvh_ratio_timeseries(collection, aoi):
        return SARService.get_index_timeseries(collection, aoi, "VVVH_ratio")

    @staticmethod
    def get_image_for_date(collection, aoi, date, index_band="VVVH_ratio"):
        next_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )

        return (
            collection.filterDate(date, next_date)
            .first()
            .select(["VV", "VH", "VVVH_ratio", "RVI", "DpRVI"])
            .clip(aoi)
        )

    @staticmethod
    def get_ratio_preview_url(image, aoi):
        return image.select("VVVH_ratio").getThumbURL(
            {
                "region": aoi.geometry().bounds().getInfo(),
                "dimensions": 900,
                "format": "png",
                "crs": "EPSG:4326",
                "min": 0.3,
                "max": 1.0,
                "palette": SARService.PLOTLY_SEQUENTIAL_PALETTE,
            }
        )

    @staticmethod
    def download_image(image, aoi, date, output_folder=None, index_band="VVVH_ratio", index_label="VV/VH Ratio"):
        url = image.getDownloadURL(
            {
                "scale": 10,
                "region": aoi.geometry().bounds().getInfo(),
                "format": "GeoTIFF",
                "crs": "EPSG:4326",
            }
        )

        response = requests.get(url, timeout=300)
        if not response.ok:
            raise RuntimeError(
                f"SAR download failed (HTTP {response.status_code}): {response.reason}"
            )

        filename = f"Sentinel1_{date}.tiff"
        base_dir = (
            output_folder
            if (output_folder and os.path.isdir(output_folder))
            else tempfile.gettempdir()
        )
        output_path = SARService._resolve_path(base_dir, filename)

        with open(output_path, "wb") as f:
            f.write(response.content)

        SARService._set_band_names(output_path, index_label)
        return output_path

    @staticmethod
    def _set_band_names(file_path, index_label="VV/VH Ratio"):
        if gdal is None:
            return

        try:
            dataset = gdal.Open(file_path, gdal.GA_Update)
            if dataset is None:
                return

            band_names = ["VV", "VH", "VV/VH Ratio", "RVI", "DpRVI"]
            for i in range(1, min(dataset.RasterCount + 1, len(band_names) + 1)):
                band = dataset.GetRasterBand(i)
                if band is not None:
                    band.SetDescription(band_names[i - 1])

            dataset = None
        except Exception:
            pass

    @staticmethod
    def _resolve_path(folder, filename):
        candidate = os.path.join(folder, filename)
        if not os.path.exists(candidate):
            return candidate

        name, ext = os.path.splitext(filename)
        counter = 1
        while True:
            candidate = os.path.join(folder, f"{name}_{counter}{ext}")
            if not os.path.exists(candidate):
                return candidate
            counter += 1
