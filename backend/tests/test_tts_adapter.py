from app.utils.tts_adapter import merge_dialogue_into_narration


def test_merge_dialogue_removes_existing_dialogue_and_orphan_attribution():
    merged = merge_dialogue_into_narration(
        "Rồi hắn khựng lại. Trong tay Tiểu Hồng có một mảnh đá đen nhánh. Tô Minh nói. Người cầm cái gì đó?",
        "Người cầm cái gì đó?",
        "Tô Minh",
    )

    assert merged == "Rồi hắn khựng lại. Trong tay Tiểu Hồng có một mảnh đá đen nhánh. Tô Minh nói. ...Người cầm cái gì đó?"


def test_merge_dialogue_does_not_repeat_speaker_prefixed_dialogue():
    merged = merge_dialogue_into_narration(
        "Tô Minh nói: Người cầm cái gì đó?",
        "Tô Minh: Người cầm cái gì đó?",
        "Tô Minh",
    )

    assert merged == "Tô Minh nói. ...Người cầm cái gì đó?"
