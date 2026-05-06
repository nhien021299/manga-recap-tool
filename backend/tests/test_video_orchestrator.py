from app.services.video_orchestrator import VideoOrchestrator


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
