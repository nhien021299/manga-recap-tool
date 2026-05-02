import time
import requests
import sys
import pprint

URL = "http://127.0.0.1:8000/api/v1/video/produce"

payload = {
  "narration_path": "D:\\AI\\Resources\\chapter_2\\chapter_2_narration_tts.json",
  "voice_key": "voice_default",
  "speed": 1.15,
  "provider": "vieneu",
  "style": "dark_xianxia_recap"
}

print("Sending request to start video pipeline...")
try:
    res = requests.post(URL, json=payload)
    res.raise_for_status()
except Exception as e:
    print("Error starting job:", e)
    if 'res' in locals():
        print(res.text)
    sys.exit(1)

job = res.json()
job_id = job["job_id"]
print(f"Job started! ID: {job_id}\nPolling progress...")

while True:
    try:
        r = requests.get(f"http://127.0.0.1:8000/api/v1/video/jobs/{job_id}")
        st = r.json()
        print(f"[{st['phase']}] {st['progress']}% - {st['detail']}")
        
        if st["phase"] in ("completed", "failed", "cancelled"):
            if st.get("error"):
                print("ERROR:", st["error"])
            print("Finished.")
            break
    except Exception as e:
        print("Polling error:", e)
        
    time.sleep(3)
