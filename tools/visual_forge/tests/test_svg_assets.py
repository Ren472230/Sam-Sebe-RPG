import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from visual_forge import compose_production_preview, inspect_asset, verify_production_manifest  # noqa: E402


class SvgProductionTests(unittest.TestCase):
    def write_svg(self, path: Path, width: int = 32, height: int = 18) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}"><rect width="{width}" height="{height}" fill="#F4F1E8"/></svg>',
            encoding="utf-8",
        )

    def test_inspect_and_verify_accept_structurally_valid_svg(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            production = root / "web/public/assets/production"
            asset = production / "village/layer.svg"
            self.write_svg(asset)
            manifest = {
                "version": 2,
                "status": "ready",
                "canvas": {"width": 960, "height": 540},
                "village": {"layers": {"architecture": "village/layer.svg"}},
            }
            production.mkdir(parents=True, exist_ok=True)
            (production / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            asset_report = inspect_asset(asset)
            self.assertEqual(asset_report["format"], "SVG")
            self.assertEqual(asset_report["mode"], "vector")
            self.assertEqual(asset_report["size"], [32, 18])

            report = verify_production_manifest(root)
            self.assertTrue(report["ok"])
            self.assertEqual(report["invalid_assets"], [])
            self.assertEqual(report["inspected_assets"][0]["format"], "SVG")

    def test_production_preview_can_emit_self_contained_svg(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            production = root / "web/public/assets/production"
            asset = production / "village/architecture.svg"
            self.write_svg(asset, 4, 4)
            manifest = {
                "version": 2,
                "status": "ready",
                "canvas": {"width": 4, "height": 4},
                "village": {
                    "layers": {
                        "sky": "",
                        "distant_nature": "",
                        "mid_nature": "",
                        "architecture": "village/architecture.svg",
                        "gameplay": "",
                        "foreground": "",
                    }
                },
            }
            (production / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            output = root / "preview.svg"
            report = compose_production_preview(root, output)
            self.assertEqual(report["layer_count"], 1)
            self.assertEqual(report["layer_slots"], ["architecture"])
            self.assertEqual(report["layers"], ["village/architecture.svg"])
            text = output.read_text(encoding="utf-8")
            self.assertIn("data:image/svg+xml;base64,", text)
            ET.parse(output)


if __name__ == "__main__":
    unittest.main()
