Place local TTS assets here.

The only supported TTS flow is now:

- provider: `vieneu`
- model: `pnnbao-ump/VieNeu-TTS-0.3B`
- mode: `standard`
- cached preset: `voice_default`

## Required layout

Reference source of truth:

```text
backend/.models/voice-cache/voice_default/reference.wav
backend/.models/voice-cache/voice_default/reference.txt
backend/.models/voice-cache/voice_default/source.mp3      # optional
backend/.models/voice-cache/voice_default/metadata.json   # optional
```

Generated preset cache:

```text
backend/.models/vieneu-voices/voices.json
backend/.models/vieneu-voices/clone-cache.json
backend/.models/vieneu-voices/voice_default.wav
backend/.models/vieneu-voices/voice_default.txt
```

## Rebuild preset

After replacing the reference clip or transcript, rebuild the cached preset with:

```bash
python backend/scripts/build_voice_default_preset.py --source-key voice_default --voice-key voice_default --device cpu
```

## Runtime diagnostics

- `GET /api/v1/system/tts`
- `GET /api/v1/system/tts?provider=vieneu`
