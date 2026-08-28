from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from PIL import Image


CANONICAL_START_VILLAGE_IDS = (
    "SKY_001",
    "DISTANT_MOUNTAINS_001",
    "DISTANT_FOREST_001",
    "MID_NATURE_001",
    "GROUND_PATH_001",
    "TAVERN_001",
    "HOUSE_002",
    "WORKSHOP_001",
    "WELL_001",
    "BUSH_001",
    "GRASS_MASS_001",
    "FOREGROUND_FLORA_001",
    "NPC_MASTER_001",
    "NPC_002",
)

ALLOWED_REGISTRY_STATUSES = {
    "active",
    "accepted-unmaterialized",
    "candidate",
    "unmaterialized",
    "rejected-slot",
}


def _load_rgba(path: str | Path) -> Image.Image:
    image = Image.open(path)
    image.load()
    return image.convert("RGBA")


def _load_mask(path: str | Path) -> Image.Image:
    image = Image.open(path)
    image.load()
    return image.convert("L")


def inspect_asset(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    raw = path.read_bytes()
    with Image.open(path) as source:
        source.load()
        source_format = source.format
        original_mode = source.mode
        has_alpha = "A" in source.getbands() or "transparency" in source.info
        rgba = source.convert("RGBA")

    alpha = rgba.getchannel("A")
    alpha_bbox = alpha.getbbox()
    alpha_min, alpha_max = alpha.getextrema()
    return {
        "path": str(path),
        "format": source_format,
        "mode": original_mode,
        "size": [rgba.width, rgba.height],
        "has_alpha": has_alpha,
        "alpha_range": [int(alpha_min), int(alpha_max)],
        "alpha_bbox": list(alpha_bbox) if alpha_bbox else None,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "byte_length": len(raw),
    }


def validate_edit(
    original_path: str | Path,
    edited_path: str | Path,
    mask_path: str | Path,
) -> dict[str, Any]:
    original = _load_rgba(original_path)
    edited = _load_rgba(edited_path)
    mask = _load_mask(mask_path)

    if original.size != edited.size or original.size != mask.size:
        raise ValueError(
            f"original, edited and mask sizes must match: "
            f"{original.size}, {edited.size}, {mask.size}"
        )

    original_pixels = original.load()
    edited_pixels = edited.load()
    mask_pixels = mask.load()
    outside_changed = 0
    inside_changed = 0

    for y in range(original.height):
        for x in range(original.width):
            if original_pixels[x, y] == edited_pixels[x, y]:
                continue
            if mask_pixels[x, y] > 0:
                inside_changed += 1
            else:
                outside_changed += 1

    return {
        "ok": outside_changed == 0,
        "size": [original.width, original.height],
        "inside_mask_changed_pixels": inside_changed,
        "outside_mask_changed_pixels": outside_changed,
    }


def compose_scene(manifest_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    canvas = manifest["canvas"]
    width = int(canvas["width"])
    height = int(canvas["height"])
    background = tuple(canvas.get("background", [0, 0, 0, 0]))
    if len(background) != 4:
        raise ValueError("canvas.background must contain 4 RGBA values")

    scene = Image.new("RGBA", (width, height), background)
    base_dir = manifest_path.parent

    indexed_layers = list(enumerate(manifest.get("layers", [])))
    indexed_layers.sort(key=lambda item: (int(item[1].get("z", 0)), item[0]))

    used_layers: list[str] = []
    for _, layer in indexed_layers:
        layer_path = (base_dir / layer["path"]).resolve()
        image = _load_rgba(layer_path)

        scale = float(layer.get("scale", 1.0))
        if scale <= 0:
            raise ValueError("layer scale must be positive")
        if scale != 1.0:
            new_size = (
                max(1, round(image.width * scale)),
                max(1, round(image.height * scale)),
            )
            image = image.resize(new_size, Image.Resampling.LANCZOS)

        opacity = float(layer.get("opacity", 1.0))
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("layer opacity must be in the range 0..1")
        if opacity != 1.0:
            alpha = image.getchannel("A").point(lambda p: round(p * opacity))
            image.putalpha(alpha)

        x = int(layer.get("x", 0))
        y = int(layer.get("y", 0))
        scene.alpha_composite(image, dest=(x, y))
        used_layers.append(str(layer["path"]))

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    scene.save(output_path, format="PNG")
    return {
        "output": str(output_path),
        "size": [width, height],
        "layer_count": len(used_layers),
        "layers": used_layers,
        "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
    }


def verify_registry(registry_path: str | Path) -> dict[str, Any]:
    registry_path = Path(registry_path)
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assets = registry.get("assets", [])
    if not isinstance(assets, list):
        raise ValueError("registry.assets must be a list")

    ids = [item.get("id") for item in assets if isinstance(item, dict)]
    canonical = list(CANONICAL_START_VILLAGE_IDS)
    duplicates = sorted({asset_id for asset_id in ids if asset_id and ids.count(asset_id) > 1})
    missing = [asset_id for asset_id in canonical if asset_id not in ids]
    unknown = sorted({asset_id for asset_id in ids if asset_id and asset_id not in canonical})
    invalid_statuses = []
    for item in assets:
        if not isinstance(item, dict):
            invalid_statuses.append({"id": None, "status": None})
            continue
        status = item.get("status")
        if status not in ALLOWED_REGISTRY_STATUSES:
            invalid_statuses.append({"id": item.get("id"), "status": status})

    ok = not duplicates and not missing and not unknown and not invalid_statuses and len(assets) == len(canonical)
    return {
        "ok": ok,
        "registry": str(registry_path),
        "asset_count": len(assets),
        "missing_ids": missing,
        "unknown_ids": unknown,
        "duplicate_ids": duplicates,
        "invalid_statuses": invalid_statuses,
    }


def _manifest_asset_paths(manifest: dict[str, Any]) -> Iterable[str]:
    village = manifest.get("village", {})
    tavern = manifest.get("tavern", {})

    for section in (village.get("layers", {}), tavern.get("layers", {})):
        if isinstance(section, dict):
            for value in section.values():
                if isinstance(value, str) and value:
                    yield value

    for section_name in ("characters", "props", "ui"):
        section = manifest.get(section_name, {})
        if isinstance(section, dict):
            for value in section.values():
                if isinstance(value, str) and value:
                    yield value


def verify_production_manifest(repo_root: str | Path) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    production_dir = repo_root / "web/public/assets/production"
    manifest_path = production_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    materialized = list(_manifest_asset_paths(manifest))
    missing: list[str] = []
    invalid: list[dict[str, str]] = []
    inspected: list[dict[str, Any]] = []

    production_resolved = production_dir.resolve()
    for relative in materialized:
        candidate = (production_dir / relative).resolve()
        try:
            candidate.relative_to(production_resolved)
        except ValueError:
            invalid.append({"path": relative, "error": "path escapes production directory"})
            continue

        if not candidate.is_file():
            missing.append(relative)
            continue

        try:
            report = inspect_asset(candidate)
            report["relative_path"] = relative
            inspected.append(report)
        except Exception as exc:  # validation command should report all failures at once
            invalid.append({"path": relative, "error": str(exc)})

    return {
        "ok": not missing and not invalid,
        "manifest": str(manifest_path),
        "manifest_version": manifest.get("version"),
        "manifest_status": manifest.get("status"),
        "materialized_layer_count": len(materialized),
        "missing_paths": missing,
        "invalid_assets": invalid,
        "inspected_assets": inspected,
    }


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Free-first deterministic visual production tools for Sam-Sebe-RPG"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    inspect_cmd = sub.add_parser("inspect")
    inspect_cmd.add_argument("asset")

    validate_cmd = sub.add_parser("validate-edit")
    validate_cmd.add_argument("original")
    validate_cmd.add_argument("edited")
    validate_cmd.add_argument("mask")

    compose_cmd = sub.add_parser("compose")
    compose_cmd.add_argument("manifest")
    compose_cmd.add_argument("output")

    verify_cmd = sub.add_parser("verify-production")
    verify_cmd.add_argument("--root", default=".")

    registry_cmd = sub.add_parser("verify-registry")
    registry_cmd.add_argument("registry")

    args = parser.parse_args()

    if args.command == "inspect":
        _print_json(inspect_asset(args.asset))
        return 0
    if args.command == "validate-edit":
        report = validate_edit(args.original, args.edited, args.mask)
        _print_json(report)
        return 0 if report["ok"] else 2
    if args.command == "compose":
        _print_json(compose_scene(args.manifest, args.output))
        return 0
    if args.command == "verify-production":
        report = verify_production_manifest(args.root)
        _print_json(report)
        return 0 if report["ok"] else 2
    if args.command == "verify-registry":
        report = verify_registry(args.registry)
        _print_json(report)
        return 0 if report["ok"] else 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
