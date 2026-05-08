from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from app import filter_signal_data, load_signal_data, read_signal_data, rsrp_to_hex, rsrp_to_rgb


class TestSignalDashboard(unittest.TestCase):
    def test_read_signal_data_existing_csv(self):
        csv_content = (
            "Latitude,Longitude,CellID,Band,RSRP_dBm,SINR_dB,TerminalType,Download_Mbps\n"
            "31.209143,121.482867,1926,n28,-94.94,5.44,Smartphone,138.21\n"
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "signal_samples.csv"
            csv_path.write_text(csv_content, encoding="utf-8")

            df = read_signal_data(csv_path)

        self.assertEqual(len(df), 1)
        self.assertEqual(df.loc[0, "Band"], "n28")
        self.assertEqual(df.loc[0, "RSRP_dBm"], -94.94)

    def test_read_signal_data_missing_csv(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_path = Path(tmp_dir) / "missing.csv"

            with self.assertRaises(FileNotFoundError):
                read_signal_data(missing_path)

    def test_cached_load_signal_data_existing_csv(self):
        csv_content = (
            "Latitude,Longitude,CellID,Band,RSRP_dBm,SINR_dB,TerminalType,Download_Mbps\n"
            "31.214219,121.484829,1457,n78,-105.47,20.67,CPE,837.84\n"
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "signal_samples.csv"
            csv_path.write_text(csv_content, encoding="utf-8")
            load_signal_data.clear()

            df = load_signal_data(str(csv_path))

        self.assertEqual(len(df), 1)
        self.assertEqual(df.loc[0, "CellID"], 1457)

    def test_cached_load_signal_data_missing_csv(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_path = Path(tmp_dir) / "missing.csv"
            load_signal_data.clear()

            with self.assertRaises(FileNotFoundError):
                load_signal_data(str(missing_path))

    def test_rsrp_hex_color_mapping(self):
        cases = {
            -89.99: "#00FF00",
            -90: "#FFFF00",
            -100: "#FFFF00",
            -110: "#FFFF00",
            -110.01: "#FF0000",
            np.nan: "#888888",
            "bad-value": "#888888",
        }

        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(rsrp_to_hex(value), expected)

    def test_rsrp_rgb_color_mapping(self):
        cases = {
            -89: [0, 255, 0],
            -90: [255, 255, 0],
            -110: [255, 255, 0],
            -111: [255, 0, 0],
            np.nan: [128, 128, 128],
            "bad-value": [128, 128, 128],
        }

        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(rsrp_to_rgb(value), expected)

    def test_filter_signal_data_by_band(self):
        df = self._sample_df()

        filtered = filter_signal_data(df, ["n78"], (-120, -70))

        self.assertEqual(len(filtered), 2)
        self.assertTrue((filtered["Band"] == "n78").all())

    def test_filter_signal_data_by_rsrp_range(self):
        df = self._sample_df()

        filtered = filter_signal_data(df, ["n28", "n78"], (-100, -90))

        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered["CellID"].tolist(), [1, 3])

    def test_filter_signal_data_combined(self):
        df = self._sample_df()

        filtered = filter_signal_data(df, ["n28"], (-100, -90))

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered.iloc[0]["CellID"], 1)
        self.assertEqual(filtered.iloc[0]["RSRP_dBm"], -95)

    @staticmethod
    def _sample_df():
        return pd.DataFrame(
            {
                "Latitude": [31.20, 31.21, 31.22, 31.23],
                "Longitude": [121.40, 121.41, 121.42, 121.43],
                "CellID": [1, 2, 3, 4],
                "Band": ["n28", "n78", "n78", "n41"],
                "RSRP_dBm": [-95, -85, -100, -112],
                "SINR_dB": [10, 20, 15, 5],
                "TerminalType": ["Smartphone", "CPE", "IoT", "Smartphone"],
                "Download_Mbps": [100, 800, 500, 60],
            }
        )


if __name__ == "__main__":
    unittest.main()
