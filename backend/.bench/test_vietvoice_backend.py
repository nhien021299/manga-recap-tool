from app.services.tts.vietvoice.vietvoice_provider import get_vietvoice_service


def main():
    service = get_vietvoice_service()

    output = service.synthesize(
        text=(
            "Tô Minh đứng chết lặng giữa màn mưa máu. "
            "Trước mắt hắn, bí mật bị chôn giấu suốt nhiều năm cuối cùng cũng lộ ra. "
            "Nhưng điều đáng sợ nhất là, kẻ đứng sau tất cả vẫn chưa hề xuất hiện."
        ),
        output_name="clone_recap_test_joined_44100.wav",
        voice_key="voice_default",
        job_id="bench_vietvoice",
    )

    print("Generated:", output)


if __name__ == "__main__":
    main()
