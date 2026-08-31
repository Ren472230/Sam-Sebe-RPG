import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from visual_forge import compose_production_preview  # noqa: E402


class ProductionPreviewScalingRegressionTests(unittest.TestCase):
    def test_materialized_layers_are_scaled_to_runtime_canvas(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            production = root / "web/public/assets/production"
            village = production / "village"
            village.mkdir(parents=True)

            architecture = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
            gameplay = Image.new("RGBA", (2, 2), (0, 0, 255, 255))
            architecture.save(village / "architecture.png")
            gameplay.save(village / "gameplay.png")

            manifest = {
                "version": 2,
                "status": "partial",
                "canvas": {"width": 4, "height": 4},
                "village": {
                    "layers": {
                        "sky": "",
                        "distant_nature": "",
                        "mid_nature": "",
                        "architecture": "village/architecture.png",
                        "gameplay": "village/gameplay.png",
                        "foreground": "",
                    }
                },
            }
            (production / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            output = root / "preview.png"
            compose_production_preview(root, output)

            with Image.open(output) as image:
                rgba = image.convert("RGBA")
                self.assertEqual(rgba.getpixel((3, 3)), (0, 0, 255, 255))


if __name__ == "__main__":
    unittest.main()
