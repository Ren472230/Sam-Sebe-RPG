from pathlib import Path


def test_readme_describes_current_playable_entrypoint() -> None:
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")

    assert (root / "RUN_STREAM_SLICE.ps1").is_file()
    assert "RUN_STREAM_SLICE.ps1 -Reset" in readme
    assert "http://127.0.0.1:5173/?stream=1" in readme
    assert "Living World" in readme
    assert "Living Conversation" in readme
    assert "docs/release/STREAM_SLICE_V1.md" in readme
    assert "## Next slice" not in readme
