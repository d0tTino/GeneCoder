import base64
from genecoder.default_visualizer import DefaultVisualizer


def test_default_visualizer_generates_plot() -> None:
    vis = DefaultVisualizer()
    result = vis.visualize("ACGT" * 25, window_size=10, step_size=5)
    assert "sequence_analysis" in result
    b64 = result["sequence_analysis"]
    assert isinstance(b64, str)
    img = base64.b64decode(b64)
    assert img.startswith(b"\x89PNG")
