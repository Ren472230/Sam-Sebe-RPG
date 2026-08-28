import json
import sys
import tempfile
import unittest
import warnings
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from visual_forge import (  # noqa: E402
    compose_scene,
    inspect_asset,
    validate_edit,
    verify_production_manifest,
    verify_registry,
)


class VisualForgeTests(unittest.TestCase):
    def make_rgba(self, path: Path, size=(16, 16), fill=(0, 0, 0, 0)) -> Image.Image:
        image = Image.new("RGBA", size, fill)
        image.save(path)
        return image

    def test_validate_edit_accepts_changes_inside_mask_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = self.make_rgba(root / "original.png", fill=(10, 20, 30, 255))
            edited = original.copy()
            edited.putpixel((8, 8), (200, 100, 50, 255))
            edited.save(root / "edited.png")

            mask = Image.new("L", original.size, 0)
            mask.putpixel((8, 8), 255)
            mask.save(root / "mask.png")

            report = validate_edit(root / "original.png", root / "edited.png", root / "mask.png")
            self.assertTrue(report["ok"])
            self.assertEqual(report["outside_mask_changed_pixels"], 0)

    def test_validate_edit_rejects_any_change_outside_mask(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = self.make_rgba(root / "original.png", fill=(10, 20, 30, 255))
            edited = original.copy()
            edited.putpixel((0, 0), (255, 0, 0, 255))
            edited.save(root / "edited.png")

            mask = Image.new("L", original.size, 0)
            mask.putpixel((8, 8), 255)
            mask.save(root / "mask.png")

            report = validate_edit(root / "original.png", root / "edited.png", root / "mask.png")
            self.assertFalse(report["ok"])
            self.assertEqual(report["outside_mask_changed_pixels"], 1)

    def test_compose_scene_is_deterministic_and_respects_z_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            red = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
            blue = Image.new("RGBA", (2, 2), (0, 0, 255, 255))
            red.save(root / "red.png")
            blue.save(root / "blue.png")
            manifest = {
                "canvas": {"width": 4, "height": 4, "background": [0, 0, 0, 0]},
                "layers": [
                    {"path": "blue.png", "x": 1, "y": 1, "z": 10},
                    {"path": "red.png", "x": 0, "y": 0, "z": 0},
                ],
            }
            (root / "scene.json").write_text(json.dumps(manifest), encoding="utf-8")

            out1 = root / "out1.png"
            out2 = root / "out2.png"
            compose_scene(root / "scene.json", out1)
            compose_scene(root / "scene.json", out2)

            self.assertEqual(out1.read_bytes(), out2.read_bytes())
            with Image.open(out1) as image:
                self.assertEqual(image.convert("RGBA").getpixel((1, 1)), (0, 0, 255, 255))
                self.assertEqual(image.convert("RGBA").getpixel((0, 0)), (255, 0, 0, 255))

    def test_inspect_asset_reports_alpha_and_bbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = Image.new("RGBA", (10, 8), (0, 0, 0, 0))
            for x in range(2, 6):
                for y in range(3, 7):
                    image.putpixel((x, y), (100, 120, 140, 255))
            image.save(root / "asset.png")

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                report = inspect_asset(root / "asset.png")
            resource_warnings = [w for w in caught if issubclass(w.category, ResourceWarning)]
            self.assertEqual(resource_warnings, [])
            self.assertEqual(report["size"], [10, 8])
            self.assertTrue(report["has_alpha"])
            self.assertEqual(report["alpha_bbox"], [2, 3, 6, 7])
            self.assertEqual(len(report["sha256"]), 64)

    def test_verify_production_manifest_checks_only_materialized_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            production = root / "web/public/assets/production"
            production.mkdir(parents=True)
            self.make_rgba(production / "layer.png", size=(32, 18), fill=(1, 2, 3, 128))
            manifest = {
                "version": 2,
                "status": "partial",
                "canvas": {"width": 960, "height": 540},
                "village": {
                    "layers": {
                        "sky": "",
                        "architecture": "layer.png",
                    }
                },
            }
            (production / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            report = verify_production_manifest(root)
            self.assertTrue(report["ok"])
            self.assertEqual(report["materialized_layer_count"], 1)
            self.assertEqual(report["missing_paths"], [])

    def test_verify_production_manifest_rejects_missing_referenced_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            production = root / "web/public/assets/production"
            production.mkdir(parents=True)
            manifest = {
                "version": 2,
                "status": "partial",
                "canvas": {"width": 960, "height": 540},
                "village": {"layers": {"architecture": "missing.webp"}},
            }
            (production / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            report = verify_production_manifest(root)
            self.assertFalse(report["ok"])
            self.assertEqual(report["missing_paths"], ["missing.webp"])

    def test_verify_registry_requires_exact_canonical_14_set(self):
        canonical = [
            "SKY_001", "DISTANT_MOUNTAINS_001", "DISTANT_FOREST_001", "MID_NATURE_001",
            "GROUND_PATH_001", "TAVERN_001", "HOUSE_002", "WORKSHOP_001", "WELL_001",
            "BUSH_001", "GRASS_MASS_001", "FOREGROUND_FLORA_001", "NPC_MASTER_001", "NPC_002",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = {
                "version": 1,
                "assets": [{"id": asset_id, "status": "unmaterialized"} for asset_id in canonical],
            }
            path = root / "registry.json"
            path.write_text(json.dumps(registry), encoding="utf-8")
            self.assertTrue(verify_registry(path)["ok"])

            registry["assets"] = registry["assets"][:-1]
            path.write_text(json.dumps(registry), encoding="utf-8")
            report = verify_registry(path)
            self.assertFalse(report["ok"])
            self.assertEqual(report["missing_ids"], ["NPC_002"])


if __name__ == "__main__":
    unittest.main()
