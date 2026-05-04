# Motion & Transition Preset-Driven Plan cho Remotion Agent

## 1. Mục tiêu

Plan này dùng để nâng cấp hệ thống dựng video recap trong project, tránh tình trạng mọi scene đều dùng chung:

- `transition = crossfade`
- `transitionDurationMs = 500`
- `motionPreset = push_in_center`
- `keyframes = []`

Mục tiêu không phải là để AI tự viết motion/keyframe tự do, mà là xây dựng một hệ thống **preset-driven**:

> Frontend/Remotion giữ bộ preset cố định.  
> Gemini hoặc LLM chỉ chọn preset, mood, intensity, SFX/VFX tags.  
> Remotion tự resolve preset thành keyframe/motion thực tế.

Cách này giúp video bớt đều, có nhịp điện ảnh hơn, nhưng vẫn kiểm soát được style, tránh lỗi render và tiết kiệm token.

---

## 2. Nguyên tắc cốt lõi

### 2.1. Không cho Gemini tự viết keyframe thô

Không yêu cầu Gemini trả về kiểu:

```json
{
  "keyframes": [
    { "frame": 0, "scale": 1 },
    { "frame": 42, "scale": 1.08 },
    { "frame": 72, "x": -20 }
  ]
}
```

Lý do:

- Dễ lệch FPS.
- Dễ lệch duration từng scene.
- Dễ lỗi khi render cả bản ngang và dọc.
- Khó QA.
- Output thiếu nhất quán.
- Tốn token không cần thiết.

### 2.2. Gemini chỉ chọn metadata cấp cao

Gemini chỉ nên trả về:

```json
{
  "sceneType": "mystery_reveal",
  "mood": "ominous",
  "transition": "blur_fade",
  "transitionDurationMs": 500,
  "motionPreset": "push_in_center",
  "motionIntensity": 0.55,
  "vfxTags": ["rain", "cold_mist"],
  "sfxTags": ["dark_pulse", "low_wind"]
}
```

### 2.3. Remotion là nơi resolve motion thật

Frontend sẽ nhận metadata rồi convert thành motion/keyframe bằng code nội bộ:

```ts
const motion = resolveMotionPreset({
  preset: scene.motionPreset,
  intensity: scene.motionIntensity,
  durationInFrames,
  orientation,
});
```

Gemini chọn “ý đồ”.  
Remotion thực thi “kỹ thuật”.

---

## 3. Kiến trúc đề xuất

```txt
Image / Scene
   ↓
Gemini / LLM Script Agent
   ↓
Narration + Scene Metadata
   ↓
JSON Output
   ↓
Frontend Remotion
   ↓
Preset Resolver
   ↓
Transition Resolver
   ↓
VFX/SFX Resolver
   ↓
Final Render
```

---

## 4. JSON schema đề xuất cho mỗi scene

Mỗi scene trong output JSON nên có dạng:

```json
{
  "imageIndex": 12,
  "imagePath": "chapter_01/scene_012.webp",
  "narration": "Nhưng càng nhìn, hắn càng thấy có gì đó không thuộc về thế giới này.",
  "sceneType": "mystery_reveal",
  "mood": "ominous",
  "motionPreset": "push_in_center",
  "motionIntensity": 0.55,
  "transition": "blur_fade",
  "transitionDurationMs": 500,
  "vfxTags": ["rain", "cold_mist"],
  "sfxTags": ["dark_pulse", "low_wind"],
  "subtitleMood": "ominous"
}
```

### Field giải thích

| Field | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---:|---|
| `imageIndex` | number | Có | Index ảnh trong chapter |
| `imagePath` | string | Có | Đường dẫn ảnh |
| `narration` | string | Có | Voiceover cho scene |
| `sceneType` | string | Có | Loại cảnh để map motion |
| `mood` | string | Có | Tâm trạng cảnh |
| `motionPreset` | string | Không | Preset chuyển động |
| `motionIntensity` | number | Không | Cường độ 0.0 đến 1.0 |
| `transition` | string | Không | Preset chuyển cảnh |
| `transitionDurationMs` | number | Không | Duration transition |
| `vfxTags` | string[] | Không | Tag hiệu ứng hình |
| `sfxTags` | string[] | Không | Tag hiệu ứng âm thanh |
| `subtitleMood` | string | Không | Mood phụ đề |

---

## 5. Bộ sceneType đề xuất

Không nên tạo quá nhiều `sceneType` ngay từ đầu. Dùng khoảng 8 loại là đủ.

```ts
export type SceneType =
  | "establishing"
  | "dialogue"
  | "inner_thought"
  | "mystery_reveal"
  | "danger_build"
  | "combat_action"
  | "shock_reveal"
  | "emotional_pause";
```

### Ý nghĩa

| sceneType | Khi dùng |
|---|---|
| `establishing` | Cảnh mở không gian, núi rừng, làng, hang động, toàn cảnh |
| `dialogue` | Cảnh có lời thoại hoặc nhân vật đang nói |
| `inner_thought` | Cảnh suy nghĩ, độc thoại, chiêm nghiệm |
| `mystery_reveal` | Cảnh phát hiện vật lạ, bí mật, điềm báo |
| `danger_build` | Cảnh nguy hiểm tăng dần, quái vật sắp xuất hiện |
| `combat_action` | Cảnh hành động, rượt đuổi, né đòn, va chạm |
| `shock_reveal` | Cảnh sốc, máu, chết chóc, twist |
| `emotional_pause` | Cảnh lặng, buồn, cô độc, mất mát |

---

## 6. Bộ mood đề xuất

```ts
export type SceneMood =
  | "calm"
  | "ominous"
  | "tense"
  | "violent"
  | "tragic"
  | "mystical"
  | "lonely"
  | "epic";
```

Mood không bắt buộc phải quyết định motion, nhưng giúp tinh chỉnh intensity, subtitle style, SFX/VFX.

---

## 7. Motion preset library

### 7.1. Bộ preset tối thiểu giai đoạn 1

```ts
export type MotionPreset =
  | "still_hold"
  | "slow_zoom_in"
  | "slow_zoom_out"
  | "push_in_center"
  | "pan_left"
  | "pan_right"
  | "pan_up"
  | "pan_down"
  | "handheld_tension"
  | "impact_shake";
```

### 7.2. Ý nghĩa từng preset

| Motion preset | Mô tả | Dùng cho |
|---|---|---|
| `still_hold` | Gần như đứng yên, chỉ có scale rất nhẹ | Đối thoại, lặng, buồn |
| `slow_zoom_in` | Zoom vào chậm | Bí ẩn, tâm lý, nguy hiểm |
| `slow_zoom_out` | Zoom ra chậm | Cảnh rộng, cô độc, thế giới lớn |
| `push_in_center` | Zoom vào tâm rõ hơn | Reveal, vật lạ, điểm nhấn |
| `pan_left` | Trượt nhẹ sang trái | Quét khung hình ngang |
| `pan_right` | Trượt nhẹ sang phải | Quét khung hình ngang |
| `pan_up` | Trượt lên | Núi, trời, khí thế, tượng đài |
| `pan_down` | Trượt xuống | Rơi, vực sâu, áp lực |
| `handheld_tension` | Rung nhẹ có kiểm soát | Căng thẳng, bất ổn |
| `impact_shake` | Shake ngắn khi impact | Sốc, đánh, sấm, máu |

---

## 8. Transition preset library

### 8.1. Bộ transition giai đoạn 1

```ts
export type TransitionPreset =
  | "crossfade"
  | "dip_to_black"
  | "flash_cut"
  | "hard_cut"
  | "blur_fade";
```

### 8.2. Ý nghĩa

| Transition | Mô tả | Dùng cho |
|---|---|---|
| `crossfade` | Hòa tan nhẹ | Default, cảnh bình thường |
| `dip_to_black` | Nhúng vào đen | Tối, bí ẩn, chuyển mood nặng |
| `flash_cut` | Chớp trắng/flash nhanh | Shock, sấm, impact |
| `hard_cut` | Cắt thẳng | Hành động nhanh, nhịp gấp |
| `blur_fade` | Mờ rồi chuyển | Hồi tưởng, bí ẩn, phát hiện |

---

## 9. Mapping sceneType → motion/transition

### 9.1. Mapping mặc định

```ts
export const SCENE_MOTION_DEFAULTS = {
  establishing: {
    motionPreset: "slow_zoom_out",
    motionIntensity: 0.35,
    transition: "crossfade",
    transitionDurationMs: 600,
  },
  dialogue: {
    motionPreset: "still_hold",
    motionIntensity: 0.25,
    transition: "crossfade",
    transitionDurationMs: 450,
  },
  inner_thought: {
    motionPreset: "slow_zoom_in",
    motionIntensity: 0.35,
    transition: "dip_to_black",
    transitionDurationMs: 550,
  },
  mystery_reveal: {
    motionPreset: "push_in_center",
    motionIntensity: 0.55,
    transition: "blur_fade",
    transitionDurationMs: 500,
  },
  danger_build: {
    motionPreset: "slow_zoom_in",
    motionIntensity: 0.65,
    transition: "dip_to_black",
    transitionDurationMs: 500,
  },
  combat_action: {
    motionPreset: "handheld_tension",
    motionIntensity: 0.75,
    transition: "hard_cut",
    transitionDurationMs: 250,
  },
  shock_reveal: {
    motionPreset: "impact_shake",
    motionIntensity: 0.85,
    transition: "flash_cut",
    transitionDurationMs: 220,
  },
  emotional_pause: {
    motionPreset: "slow_zoom_out",
    motionIntensity: 0.25,
    transition: "crossfade",
    transitionDurationMs: 650,
  },
} as const;
```

### 9.2. Rule điều chỉnh bằng mood

```ts
export const MOOD_INTENSITY_MODIFIER = {
  calm: -0.15,
  lonely: -0.1,
  tragic: -0.05,
  mystical: 0.05,
  ominous: 0.1,
  tense: 0.15,
  violent: 0.2,
  epic: 0.15,
} as const;
```

Ví dụ:

```ts
const baseIntensity = 0.55;
const moodModifier = MOOD_INTENSITY_MODIFIER[mood] ?? 0;
const finalIntensity = clamp(baseIntensity + moodModifier, 0.1, 1.0);
```

---

## 10. Fallback rules bắt buộc

Bất kỳ field nào thiếu hoặc sai phải fallback an toàn.

```ts
const DEFAULT_RENDER_EFFECTS = {
  transition: "crossfade",
  transitionDurationMs: 500,
  motionPreset: "push_in_center",
  motionIntensity: 0.4,
  vfxTags: [],
  sfxTags: [],
};
```

Rule:

```ts
if (!isValidMotionPreset(scene.motionPreset)) {
  scene.motionPreset = defaultsBySceneType.motionPreset ?? "push_in_center";
}

if (!isValidTransition(scene.transition)) {
  scene.transition = defaultsBySceneType.transition ?? "crossfade";
}

if (typeof scene.motionIntensity !== "number") {
  scene.motionIntensity = defaultsBySceneType.motionIntensity ?? 0.4;
}

scene.motionIntensity = clamp(scene.motionIntensity, 0.1, 1.0);
```

---

## 11. Remotion implementation plan

### 11.1. File structure đề xuất

```txt
src/
  remotion/
    effects/
      motionPresets.ts
      transitionPresets.ts
      effectSchema.ts
      effectResolver.ts
      vfxResolver.ts
      sfxResolver.ts
    components/
      StepRender.tsx
      SceneImageMotion.tsx
      SceneTransition.tsx
      Subtitle.tsx
```

---

## 12. effectSchema.ts

Tạo schema/type cho metadata.

```ts
export const MOTION_PRESETS = [
  "still_hold",
  "slow_zoom_in",
  "slow_zoom_out",
  "push_in_center",
  "pan_left",
  "pan_right",
  "pan_up",
  "pan_down",
  "handheld_tension",
  "impact_shake",
] as const;

export type MotionPreset = typeof MOTION_PRESETS[number];

export const TRANSITION_PRESETS = [
  "crossfade",
  "dip_to_black",
  "flash_cut",
  "hard_cut",
  "blur_fade",
] as const;

export type TransitionPreset = typeof TRANSITION_PRESETS[number];

export const SCENE_TYPES = [
  "establishing",
  "dialogue",
  "inner_thought",
  "mystery_reveal",
  "danger_build",
  "combat_action",
  "shock_reveal",
  "emotional_pause",
] as const;

export type SceneType = typeof SCENE_TYPES[number];

export const SCENE_MOODS = [
  "calm",
  "ominous",
  "tense",
  "violent",
  "tragic",
  "mystical",
  "lonely",
  "epic",
] as const;

export type SceneMood = typeof SCENE_MOODS[number];

export type SceneEffectMetadata = {
  sceneType?: SceneType;
  mood?: SceneMood;
  motionPreset?: MotionPreset;
  motionIntensity?: number;
  transition?: TransitionPreset;
  transitionDurationMs?: number;
  vfxTags?: string[];
  sfxTags?: string[];
  subtitleMood?: string;
};
```

---

## 13. effectResolver.ts

Tạo resolver để merge:

1. Default toàn cục.
2. Default theo sceneType.
3. Metadata từ Gemini.
4. Clamp/validate.

```ts
import {
  MOTION_PRESETS,
  TRANSITION_PRESETS,
  SceneEffectMetadata,
  SceneType,
  SceneMood,
} from "./effectSchema";

const DEFAULT_RENDER_EFFECTS = {
  transition: "crossfade",
  transitionDurationMs: 500,
  motionPreset: "push_in_center",
  motionIntensity: 0.4,
  vfxTags: [],
  sfxTags: [],
} as const;

const SCENE_MOTION_DEFAULTS: Record<SceneType, any> = {
  establishing: {
    motionPreset: "slow_zoom_out",
    motionIntensity: 0.35,
    transition: "crossfade",
    transitionDurationMs: 600,
  },
  dialogue: {
    motionPreset: "still_hold",
    motionIntensity: 0.25,
    transition: "crossfade",
    transitionDurationMs: 450,
  },
  inner_thought: {
    motionPreset: "slow_zoom_in",
    motionIntensity: 0.35,
    transition: "dip_to_black",
    transitionDurationMs: 550,
  },
  mystery_reveal: {
    motionPreset: "push_in_center",
    motionIntensity: 0.55,
    transition: "blur_fade",
    transitionDurationMs: 500,
  },
  danger_build: {
    motionPreset: "slow_zoom_in",
    motionIntensity: 0.65,
    transition: "dip_to_black",
    transitionDurationMs: 500,
  },
  combat_action: {
    motionPreset: "handheld_tension",
    motionIntensity: 0.75,
    transition: "hard_cut",
    transitionDurationMs: 250,
  },
  shock_reveal: {
    motionPreset: "impact_shake",
    motionIntensity: 0.85,
    transition: "flash_cut",
    transitionDurationMs: 220,
  },
  emotional_pause: {
    motionPreset: "slow_zoom_out",
    motionIntensity: 0.25,
    transition: "crossfade",
    transitionDurationMs: 650,
  },
};

const MOOD_INTENSITY_MODIFIER: Partial<Record<SceneMood, number>> = {
  calm: -0.15,
  lonely: -0.1,
  tragic: -0.05,
  mystical: 0.05,
  ominous: 0.1,
  tense: 0.15,
  violent: 0.2,
  epic: 0.15,
};

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function isValidMotionPreset(value?: string) {
  return !!value && MOTION_PRESETS.includes(value as any);
}

function isValidTransition(value?: string) {
  return !!value && TRANSITION_PRESETS.includes(value as any);
}

export function resolveSceneEffects(input: SceneEffectMetadata = {}) {
  const sceneDefaults = input.sceneType
    ? SCENE_MOTION_DEFAULTS[input.sceneType]
    : {};

  const merged = {
    ...DEFAULT_RENDER_EFFECTS,
    ...sceneDefaults,
    ...input,
  };

  const moodModifier = input.mood
    ? MOOD_INTENSITY_MODIFIER[input.mood] ?? 0
    : 0;

  const motionIntensity = clamp(
    Number(merged.motionIntensity ?? DEFAULT_RENDER_EFFECTS.motionIntensity) + moodModifier,
    0.1,
    1.0
  );

  return {
    transition: isValidTransition(merged.transition)
      ? merged.transition
      : DEFAULT_RENDER_EFFECTS.transition,

    transitionDurationMs: clamp(
      Number(merged.transitionDurationMs ?? DEFAULT_RENDER_EFFECTS.transitionDurationMs),
      180,
      800
    ),

    motionPreset: isValidMotionPreset(merged.motionPreset)
      ? merged.motionPreset
      : DEFAULT_RENDER_EFFECTS.motionPreset,

    motionIntensity,

    vfxTags: Array.isArray(merged.vfxTags) ? merged.vfxTags : [],
    sfxTags: Array.isArray(merged.sfxTags) ? merged.sfxTags : [],
    subtitleMood: merged.subtitleMood ?? input.mood ?? "default",
  };
}
```

---

## 14. motionPresets.ts

Resolver chuyển `motionPreset + intensity + duration` thành transform.

```ts
import { interpolate, spring } from "remotion";
import { MotionPreset } from "./effectSchema";

type ResolveMotionArgs = {
  frame: number;
  durationInFrames: number;
  preset: MotionPreset;
  intensity: number;
};

export function resolveMotionStyle({
  frame,
  durationInFrames,
  preset,
  intensity,
}: ResolveMotionArgs): React.CSSProperties {
  const safeDuration = Math.max(durationInFrames, 1);
  const progress = frame / safeDuration;

  const zoomSmall = 1 + 0.025 * intensity;
  const zoomMedium = 1 + 0.06 * intensity;
  const panAmount = 28 * intensity;
  const shakeAmount = 8 * intensity;

  switch (preset) {
    case "still_hold": {
      const scale = interpolate(frame, [0, safeDuration], [1, zoomSmall]);
      return {
        transform: `scale(${scale})`,
      };
    }

    case "slow_zoom_in": {
      const scale = interpolate(frame, [0, safeDuration], [1, zoomMedium]);
      return {
        transform: `scale(${scale})`,
      };
    }

    case "slow_zoom_out": {
      const scale = interpolate(frame, [0, safeDuration], [zoomMedium, 1]);
      return {
        transform: `scale(${scale})`,
      };
    }

    case "push_in_center": {
      const scale = interpolate(frame, [0, safeDuration], [1, 1 + 0.09 * intensity]);
      return {
        transform: `scale(${scale})`,
      };
    }

    case "pan_left": {
      const x = interpolate(frame, [0, safeDuration], [panAmount, -panAmount]);
      return {
        transform: `scale(${1 + 0.04 * intensity}) translateX(${x}px)`,
      };
    }

    case "pan_right": {
      const x = interpolate(frame, [0, safeDuration], [-panAmount, panAmount]);
      return {
        transform: `scale(${1 + 0.04 * intensity}) translateX(${x}px)`,
      };
    }

    case "pan_up": {
      const y = interpolate(frame, [0, safeDuration], [panAmount, -panAmount]);
      return {
        transform: `scale(${1 + 0.04 * intensity}) translateY(${y}px)`,
      };
    }

    case "pan_down": {
      const y = interpolate(frame, [0, safeDuration], [-panAmount, panAmount]);
      return {
        transform: `scale(${1 + 0.04 * intensity}) translateY(${y}px)`,
      };
    }

    case "handheld_tension": {
      const x = Math.sin(frame * 0.45) * shakeAmount * 0.35;
      const y = Math.cos(frame * 0.38) * shakeAmount * 0.25;
      const scale = 1 + 0.04 * intensity;
      return {
        transform: `scale(${scale}) translate(${x}px, ${y}px)`,
      };
    }

    case "impact_shake": {
      const decay = Math.max(0, 1 - progress * 4);
      const x = Math.sin(frame * 1.4) * shakeAmount * decay;
      const y = Math.cos(frame * 1.1) * shakeAmount * decay;
      const scale = 1 + 0.05 * intensity;
      return {
        transform: `scale(${scale}) translate(${x}px, ${y}px)`,
      };
    }

    default:
      return {
        transform: "scale(1.02)",
      };
  }
}
```

---

## 15. transitionPresets.ts

Transition resolver trả về style overlay hoặc opacity.

```ts
import { interpolate } from "remotion";
import { TransitionPreset } from "./effectSchema";

type ResolveTransitionArgs = {
  frame: number;
  durationInFrames: number;
  transitionDurationInFrames: number;
  preset: TransitionPreset;
};

export function resolveSceneOpacity({
  frame,
  durationInFrames,
  transitionDurationInFrames,
  preset,
}: ResolveTransitionArgs) {
  const d = Math.min(transitionDurationInFrames, Math.floor(durationInFrames / 3));

  if (preset === "hard_cut") {
    return 1;
  }

  return interpolate(
    frame,
    [0, d, durationInFrames - d, durationInFrames],
    [0, 1, 1, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }
  );
}

export function resolveTransitionOverlay({
  frame,
  durationInFrames,
  transitionDurationInFrames,
  preset,
}: ResolveTransitionArgs): React.CSSProperties | null {
  const d = Math.min(transitionDurationInFrames, Math.floor(durationInFrames / 3));

  if (preset === "dip_to_black") {
    const opacity = interpolate(
      frame,
      [0, d, durationInFrames - d, durationInFrames],
      [1, 0, 0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );

    return {
      background: "black",
      opacity,
      pointerEvents: "none",
    };
  }

  if (preset === "flash_cut") {
    const opacity = interpolate(
      frame,
      [0, Math.max(2, d * 0.35), d],
      [0.8, 0.15, 0],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );

    return {
      background: "white",
      opacity,
      mixBlendMode: "screen",
      pointerEvents: "none",
    };
  }

  if (preset === "blur_fade") {
    const blur = interpolate(
      frame,
      [0, d, durationInFrames - d, durationInFrames],
      [8, 0, 0, 8],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );

    return {
      backdropFilter: `blur(${blur}px)`,
      pointerEvents: "none",
    };
  }

  return null;
}
```

---

## 16. Tích hợp vào StepRender.tsx

### 16.1. Trước khi sửa

Hiện tại logic thường giống:

```ts
const transition = "crossfade";
const transitionDurationMs = 500;
const motionPreset = "push_in_center";
const keyframes = [];
```

### 16.2. Sau khi sửa

```tsx
import { useCurrentFrame, useVideoConfig, AbsoluteFill } from "remotion";
import { resolveSceneEffects } from "../effects/effectResolver";
import { resolveMotionStyle } from "../effects/motionPresets";
import {
  resolveSceneOpacity,
  resolveTransitionOverlay,
} from "../effects/transitionPresets";

export function StepRender({ scene }: { scene: any }) {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const effects = resolveSceneEffects({
    sceneType: scene.sceneType,
    mood: scene.mood,
    motionPreset: scene.motionPreset,
    motionIntensity: scene.motionIntensity,
    transition: scene.transition,
    transitionDurationMs: scene.transitionDurationMs,
    vfxTags: scene.vfxTags,
    sfxTags: scene.sfxTags,
    subtitleMood: scene.subtitleMood,
  });

  const transitionDurationInFrames = Math.round(
    (effects.transitionDurationMs / 1000) * fps
  );

  const motionStyle = resolveMotionStyle({
    frame,
    durationInFrames,
    preset: effects.motionPreset,
    intensity: effects.motionIntensity,
  });

  const opacity = resolveSceneOpacity({
    frame,
    durationInFrames,
    transitionDurationInFrames,
    preset: effects.transition,
  });

  const overlayStyle = resolveTransitionOverlay({
    frame,
    durationInFrames,
    transitionDurationInFrames,
    preset: effects.transition,
  });

  return (
    <AbsoluteFill style={{ backgroundColor: "black", overflow: "hidden" }}>
      <AbsoluteFill style={{ opacity }}>
        <img
          src={scene.imagePath}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            ...motionStyle,
          }}
        />
      </AbsoluteFill>

      {overlayStyle && <AbsoluteFill style={overlayStyle} />}

      {/* Subtitle component giữ logic subtitle hiện tại */}
      {/* <Subtitle text={scene.narration} mood={effects.subtitleMood} /> */}
    </AbsoluteFill>
  );
}
```

---

## 17. Prompt cho Gemini Script Agent

Thêm đoạn này vào prompt tạo narration/script:

```md
Ngoài narration, hãy trả thêm metadata dựng video cho từng image/scene.

Không được viết keyframe thô.
Không được viết code animation.
Chỉ được chọn trong danh sách preset cho phép.

Allowed sceneType:
- establishing
- dialogue
- inner_thought
- mystery_reveal
- danger_build
- combat_action
- shock_reveal
- emotional_pause

Allowed mood:
- calm
- ominous
- tense
- violent
- tragic
- mystical
- lonely
- epic

Allowed motionPreset:
- still_hold
- slow_zoom_in
- slow_zoom_out
- push_in_center
- pan_left
- pan_right
- pan_up
- pan_down
- handheld_tension
- impact_shake

Allowed transition:
- crossfade
- dip_to_black
- flash_cut
- hard_cut
- blur_fade

motionIntensity:
- Số từ 0.1 đến 1.0.
- Cảnh bình thường: 0.25-0.45.
- Cảnh bí ẩn/căng thẳng: 0.45-0.7.
- Cảnh hành động/sốc: 0.7-0.9.
- Không dùng 1.0 trừ khi thật sự là cảnh cực mạnh.

transitionDurationMs:
- hard_cut: 180-250
- flash_cut: 180-260
- crossfade: 400-650
- dip_to_black: 450-700
- blur_fade: 450-650

Output JSON cho mỗi scene phải có dạng:
{
  "imageIndex": number,
  "narration": string,
  "sceneType": string,
  "mood": string,
  "motionPreset": string,
  "motionIntensity": number,
  "transition": string,
  "transitionDurationMs": number,
  "vfxTags": string[],
  "sfxTags": string[],
  "subtitleMood": string
}

Nếu không chắc nên chọn gì, ưu tiên:
- transition: crossfade
- motionPreset: slow_zoom_in hoặc push_in_center
- motionIntensity: 0.4
```

---

## 18. Agent task prompt

Dùng prompt này cho coding agent:

```md
Bạn hãy refactor hệ thống transition/motion trong Remotion theo hướng preset-driven.

Hiện tại StepRender.tsx đang hardcoded:
- transition luôn crossfade 500ms
- motionPreset luôn push_in_center
- keyframes là mảng rỗng

Yêu cầu:
1. Tạo thư mục effect/preset cho Remotion:
   - effectSchema.ts
   - effectResolver.ts
   - motionPresets.ts
   - transitionPresets.ts

2. Định nghĩa allowed sceneType, mood, motionPreset, transition theo plan.

3. Tạo resolveSceneEffects để:
   - đọc metadata từ scene JSON
   - fallback nếu thiếu hoặc sai field
   - map sceneType sang default motion/transition
   - mood có thể điều chỉnh intensity
   - clamp motionIntensity từ 0.1 đến 1.0
   - clamp transitionDurationMs từ 180 đến 800

4. Tạo resolveMotionStyle:
   - nhận frame, durationInFrames, preset, intensity
   - trả về React.CSSProperties transform
   - hỗ trợ các preset:
     still_hold, slow_zoom_in, slow_zoom_out, push_in_center,
     pan_left, pan_right, pan_up, pan_down,
     handheld_tension, impact_shake

5. Tạo transition resolver:
   - resolveSceneOpacity
   - resolveTransitionOverlay
   - hỗ trợ:
     crossfade, dip_to_black, flash_cut, hard_cut, blur_fade

6. Update StepRender.tsx:
   - Không hardcode transition/motion nữa.
   - Đọc từ scene metadata.
   - Nếu thiếu metadata vẫn render bằng fallback:
     crossfade 500ms + push_in_center + intensity 0.4.
   - Không phá subtitle component hiện có.
   - Không phá render preview hiện có.

7. Không cho phép custom keyframe từ JSON ở phase này.
   - Nếu scene có keyframes thì bỏ qua.
   - Motion phải do resolver nội bộ sinh ra.

8. Test:
   - Render/preview ít nhất 3 scene:
     a. scene bình thường không có metadata
     b. scene mystery_reveal
     c. scene combat_action hoặc shock_reveal
   - Đảm bảo không crash khi metadata thiếu field.
```

---

## 19. QA checklist

Sau khi agent sửa xong, kiểm tra:

### 19.1. Functional

- [ ] Scene không có metadata vẫn render được.
- [ ] Scene có metadata đúng preset render đúng.
- [ ] Scene có preset sai fallback được.
- [ ] `motionIntensity` dưới 0.1 được clamp lên 0.1.
- [ ] `motionIntensity` trên 1.0 được clamp về 1.0.
- [ ] `transitionDurationMs` quá thấp/quá cao được clamp.
- [ ] `hard_cut` không bị fade kỳ lạ.
- [ ] `flash_cut` không trắng quá lâu.
- [ ] `impact_shake` không rung quá đau mắt.

### 19.2. Visual

- [ ] Cảnh tĩnh không bị zoom quá mạnh.
- [ ] Cảnh bí ẩn có cảm giác bị kéo vào.
- [ ] Cảnh hành động có nhịp nhanh hơn.
- [ ] Cảnh shock có impact nhưng không lố.
- [ ] Bản dọc không bị motion làm lộ viền ảnh.
- [ ] Bản ngang không bị pan quá xa.
- [ ] Subtitle không bị ảnh hưởng.

### 19.3. Performance

- [ ] Không dùng hiệu ứng quá nặng.
- [ ] Không thêm dependency lớn nếu chưa cần.
- [ ] Không tạo blur quá nặng trên toàn video nếu máy render yếu.
- [ ] Có fallback nếu `backdropFilter`/blur làm preview chậm.

---

## 20. Lộ trình triển khai

### Phase 1: Safe preset system

- Tách hardcode khỏi `StepRender.tsx`.
- Tạo resolver.
- Dùng metadata nếu có.
- Fallback nếu không có.
- Chưa thêm SFX/VFX thực sự.

Kết quả: video bớt đều, ít rủi ro.

### Phase 2: Gemini metadata

- Update script prompt để Gemini trả thêm:
  - `sceneType`
  - `mood`
  - `motionPreset`
  - `motionIntensity`
  - `transition`
  - `transitionDurationMs`
  - `sfxTags`
  - `vfxTags`
- Validate JSON trước khi đưa vào render.

Kết quả: mỗi cảnh có nhịp riêng.

### Phase 3: SFX/VFX resolver

- Map `sfxTags` sang local audio library.
- Map `vfxTags` sang overlay nhẹ:
  - rain
  - mist
  - ember
  - lightning_flash
  - dark_vignette
  - blood_splatter_subtle
- Chỉ dùng tag, không để Gemini tự tạo file hoặc tự chọn link lung tung.

Kết quả: video có âm thanh và không khí phong phú hơn.

### Phase 4: QA scoring

Thêm preview/debug overlay:

```tsx
{debug && (
  <div>
    {scene.sceneType} / {effects.motionPreset} / {effects.transition}
  </div>
)}
```

Dùng để xem nhanh mỗi scene đang chạy effect gì.

---

## 21. VFX tag gợi ý cho phase sau

```ts
export type VfxTag =
  | "rain"
  | "cold_mist"
  | "embers"
  | "dark_vignette"
  | "lightning_flash"
  | "blood_splatter_subtle"
  | "dust"
  | "speed_lines";
```

### Mapping

| vfxTag | Dùng cho |
|---|---|
| `rain` | Cảnh mưa, rừng, đêm |
| `cold_mist` | Núi, bí ẩn, hang động |
| `embers` | Cháy, làng bị đốt, chiến trường |
| `dark_vignette` | Cảnh u ám, tâm lý |
| `lightning_flash` | Sấm, thiên tượng |
| `blood_splatter_subtle` | Cảnh máu, giết chóc |
| `dust` | Va chạm, đổ nát |
| `speed_lines` | Hành động nhanh |

---

## 22. SFX tag gợi ý cho phase sau

```ts
export type SfxTag =
  | "low_wind"
  | "dark_pulse"
  | "heartbeat"
  | "thunder"
  | "impact_hit"
  | "whoosh"
  | "monster_growl"
  | "fire_crackle"
  | "silence_drop";
```

### Mapping

| sfxTag | Dùng cho |
|---|---|
| `low_wind` | Rừng, núi, cảnh lạnh |
| `dark_pulse` | Bí ẩn, vật lạ, reveal |
| `heartbeat` | Căng thẳng, sợ hãi |
| `thunder` | Sấm, bão |
| `impact_hit` | Đòn đánh, va chạm |
| `whoosh` | Chuyển động nhanh |
| `monster_growl` | Quái vật |
| `fire_crackle` | Cháy, đêm lửa |
| `silence_drop` | Khoảnh khắc sốc, cliffhanger |

---

## 23. Quy tắc tránh lạm dụng

- Không dùng `impact_shake` quá 2-3 lần mỗi phút.
- Không dùng `flash_cut` liên tục.
- Không dùng `handheld_tension` cho cảnh đọc thoại dài.
- Không dùng `pan_left/right` nếu ảnh đã crop sát nhân vật.
- Không dùng intensity > 0.85 trừ cảnh cực mạnh.
- Không dùng nhiều VFX cùng lúc trong phase đầu.
- Mỗi scene chỉ nên có 0-2 `vfxTags`.
- Mỗi scene chỉ nên có 0-2 `sfxTags`.

---

## 24. Sweet spot khuyến nghị

Cho project hiện tại, cấu hình mặc định nên là:

```ts
{
  transition: "crossfade",
  transitionDurationMs: 500,
  motionPreset: "slow_zoom_in",
  motionIntensity: 0.35
}
```

Riêng cảnh phát hiện vật lạ/bí ẩn:

```ts
{
  sceneType: "mystery_reveal",
  transition: "blur_fade",
  transitionDurationMs: 500,
  motionPreset: "push_in_center",
  motionIntensity: 0.55,
  sfxTags: ["dark_pulse"],
  vfxTags: ["cold_mist"]
}
```

Cảnh hành động:

```ts
{
  sceneType: "combat_action",
  transition: "hard_cut",
  transitionDurationMs: 220,
  motionPreset: "handheld_tension",
  motionIntensity: 0.7,
  sfxTags: ["whoosh", "impact_hit"],
  vfxTags: ["speed_lines"]
}
```

Cảnh shock:

```ts
{
  sceneType: "shock_reveal",
  transition: "flash_cut",
  transitionDurationMs: 200,
  motionPreset: "impact_shake",
  motionIntensity: 0.8,
  sfxTags: ["silence_drop", "dark_pulse"],
  vfxTags: ["dark_vignette"]
}
```

---

## 25. Kết luận kỹ thuật

Không nên chọn một trong hai cực đoan:

1. Hardcoded toàn bộ: an toàn nhưng video đều, thiếu nhịp.
2. Gemini tự viết effect/keyframe: linh hoạt nhưng khó kiểm soát, dễ lỗi, tốn token.

Nên dùng:

```txt
Preset cố định trong code
+
Gemini chọn metadata nhẹ
+
Resolver kiểm soát motion/transition
+
Fallback an toàn
```

Đây là hướng hợp nhất cho recap pipeline:

- Ít lỗi.
- Dễ debug.
- Dễ QA.
- Dễ mở rộng.
- Không phá frontend hiện tại.
- Không tốn token quá nhiều.
- Vẫn tạo cảm giác video có đạo diễn hình ảnh, không chỉ là slideshow.
