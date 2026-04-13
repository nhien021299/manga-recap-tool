export const generateSpeech = async (
  apiKey: string, 
  text: string, 
  voiceId: string = 'pNInz6obpgDQGcFmaJgB' // Adam - High quality default
): Promise<Blob> => {
  if (!apiKey) throw new Error("Vui lòng nhập ElevenLabs API Key");

  const url = `https://api.elevenlabs.io/v1/text-to-speech/${voiceId}`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'xi-api-key': apiKey,
      'Accept': 'audio/mpeg'
    },
    body: JSON.stringify({
      text,
      model_id: "eleven_multilingual_v2",
      voice_settings: {
        stability: 0.5,
        similarity_boost: 0.75,
        style: 0.0,
        use_speaker_boost: true
      }
    })
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail?.status || "Lỗi khi gọi ElevenLabs API");
  }

  return await response.blob();
};
