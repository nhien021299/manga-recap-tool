# Product Requirements Document (PRD): Client-Side Manga Recap Video Generator

## 1. Project Overview
Build a personal, 100% client-side web application that automates the creation of recap/review videos from Manga/Webtoon chapters. The app processes images, detects characters, generates scripts via LLM, synthesizes speech, and renders an MP4 video directly in the browser using WebAssembly.

**No Backend is allowed.** All processing must happen in the browser to save server costs and ensure privacy.

## 2. Tech Stack Core
- **Framework:** React 18 + TypeScript + Vite.
- **Styling:** Tailwind CSS + shadcn/ui (for quick, accessible UI components).
- **State Management:** Zustand.
- **Storage:** `localforage` (IndexedDB) for caching large blobs/images, `localStorage` for API Keys.
- **Image Processing:** HTML5 Canvas API & `opencv.js` (WebAssembly).
- **Face/Character Detection:** `face-api.js` (or `@mediapipe/tasks-vision`).
- **LLM Integration:** Direct REST API calls to Google Gemini 3 Flash (Multimodal).
- **Text-to-Speech (TTS):** Direct REST API calls to ElevenLabs or Viettel AI.
- **Video Rendering:** `@ffmpeg/ffmpeg` (FFmpeg.wasm).

---

## 3. Application Architecture & Data Flow

### Phase 1: Global Setup & Config
- **UI:** A Settings Modal/Page.
- **Action:** User inputs API Keys (Gemini API Key, ElevenLabs API Key).
- **Storage:** Save to `localStorage`. Provide Zustand actions to retrieve these keys before making network requests.

### Phase 2: Upload & Panel Extraction (Image Processing Module)
- **Input:** User uploads a long vertical image (Webtoon chapter) or multiple standard pages.
- **Action:** - Draw image on an off-screen Canvas.
  - Algorithm: Scan horizontal pixel rows. Identify large, continuous white/black areas as boundaries to slice the image into individual panels.
  - (Optional fallback) Use `opencv.js` for contour detection to crop irregular panels.
- **Output:** Array of Panel Objects `{ id, blob, base64, characterTags: [] }`. Save to Zustand & IndexedDB.

### Phase 3: Character Tracking (Computer Vision Module)
- **Input:** Extracted Panel Objects.
- **Action:**
  - Run `face-api.js` over each panel to detect faces.
  - Group similar face vectors (Clustering).
  - **UI:** Present unique faces to the user. User assigns a name tag (e.g., "Tô Minh").
  - Auto-tag subsequent panels containing matching face vectors.
- **Output:** Update Panel Objects in Zustand with specific character tags.

### Phase 4: Script Generation (LLM Module)
- **Input:** Sequentially ordered Panel Objects (converted to compressed Base64) + Character Tags.
- **Action:** - Call Gemini 1.5 Flash API.
  - **System Prompt:** "You are a Manga Recap Video scriptwriter. Analyze the provided manga panels sequentially. Characters identified: [tags]. Write a highly engaging, fast-paced Vietnamese recap script. Output strictly as a JSON array of objects: `[{ panelId: string, narrationText: string, emotion: string }]`."
- **Output:** Parse the JSON response. 
- **UI:** Display a Timeline/List view where the user can manually edit/refine the generated `narrationText`.

### Phase 5: Voice Synthesis (TTS Module)
- **Input:** The edited JSON array from Phase 4.
- **Action:**
  - Iterate through the array. Call ElevenLabs/TTS API for each `narrationText`.
  - Receive Audio `ArrayBuffer`, convert to `Blob`, and generate `BlobURL`.
  - Calculate the audio duration using `HTMLAudioElement` or Web Audio API.
- **Output:** Update Timeline Zustand store: `{ panelId, imageBlob, audioBlob, audioDuration }`.
- **UI:** Provide a play button to preview the audio for each panel.

### Phase 6: Video Rendering (FFmpeg.wasm Module)
- **Input:** Timeline Zustand store (Images and matching Audio files).
- **Action:**
  - Load `@ffmpeg/ffmpeg` core.
  - Write all image blobs and audio blobs to the FFmpeg virtual File System (MEMFS).
  - Generate an FFmpeg command to:
    1. Turn each image into a video clip matching its audio duration (`-loop 1 -t <audioDuration>`).
    2. Add a subtle zoom-in effect (`zoompan=z='min(zoom+0.0015,1.5)'`).
    3. Concatenate all generated clips.
    4. Mix in the audio tracks.
    5. Hardcode subtitles based on the `narrationText` (by generating a `.srt` file in MEMFS).
  - Run the `ffmpeg.exec()` command.
- **Output:** Retrieve the final `.mp4` from MEMFS. Trigger an auto-download in the browser.

---

## 4. Initial Task for the AI Agent
1. Initialize the Vite + React + TS project.
2. Setup Tailwind CSS & shadcn/ui.
3. Create the standard folder structure (`/components`, `/store`, `/lib/ffmpeg`, `/lib/gemini`, etc.).
4. Create the Zustand store (`useRecapStore.ts`) defining the interfaces for `Panel`, `Character`, and `TimelineItem` based on the data flow above.
5. Build the Settings component to handle API Key storage.

**Please confirm understanding and proceed with Task 1 to 5.**