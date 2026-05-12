from app.services.video_orchestrator import VideoOrchestrator


def test_parse_remotion_percent_progress():
    service = VideoOrchestrator.__new__(VideoOrchestrator)

    assert service._parse_remotion_progress("Rendering frames 42%", 1000) == 0.42


def test_parse_remotion_frame_pair_progress():
    service = VideoOrchestrator.__new__(VideoOrchestrator)

    assert service._parse_remotion_progress("Rendered 250/1000", 1000) == 0.25


def test_parse_remotion_single_frame_progress_uses_estimated_total():
    service = VideoOrchestrator.__new__(VideoOrchestrator)

    assert service._parse_remotion_progress("frame=250 fps=30", 1000) == 0.25


def test_remotion_quality_flags_use_vertical_compression_profile():
    service = VideoOrchestrator.__new__(VideoOrchestrator)

    assert service._remotion_quality_flags(width=1080, height=1920) == [
        "--crf=23",
        "--pixel-format=yuv420p",
    ]


def test_remotion_quality_flags_use_horizontal_quality_profile():
    service = VideoOrchestrator.__new__(VideoOrchestrator)

    assert service._remotion_quality_flags(width=1920, height=1080) == [
        "--crf=21",
        "--pixel-format=yuv420p",
    ]
