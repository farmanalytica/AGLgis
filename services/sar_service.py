import os
import tempfile

import ee
import requests
from ee_s1_ard import S1ARDImageCollection
from datetime import datetime, timedelta


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
    def get_vvvh_ratio_timeseries(collection, aoi):
        def get_mean(image):
            stats = image.select("VVVH_ratio").reduceRegion(
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
                    "VVVH_ratio_mean": stats.get("VVVH_ratio"),
                },
            )

        result = collection.map(get_mean).getInfo()

        data = []
        for feature in result["features"]:
            properties = feature.get("properties", {})
            data.append(
                {
                    "dates": properties.get("date"),
                    "AOI_average": properties.get("VVVH_ratio_mean"),
                }
            )

        return data

    @staticmethod
    def get_image_for_date(collection, aoi, date):
        next_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )

        return (
            collection.filterDate(date, next_date)
            .first()
            .select(["VV", "VH", "VVVH_ratio"])
            .clip(aoi)
        )

    @staticmethod
    def get_ratio_preview_url(image, aoi):
        return image.select("VVVH_ratio").getThumbURL(
            {
                "region": aoi.geometry().bounds().getInfo(),
                "dimensions": 900,
                "format": "png",
                "min": 0.3,
                "max": 1.0,
                "palette": SARService.PLOTLY_SEQUENTIAL_PALETTE,
            }
        )

    @staticmethod
    def download_image(image, aoi, date, output_folder=None):
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

        return output_path

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
