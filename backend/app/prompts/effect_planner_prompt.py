"""Prompt templates for video effect planner."""

EFFECT_PLANNER_PROMPT_V2 = """
You are an effect planner for a Remotion manga recap renderer.
Return raw JSON only. No markdown. No explanation.

Choose only from allowed values.
Do not invent tags.
Use max 2 vfx tags per scene.
Use hard_cut only for combat/impact.
Use dip_to_black only for tragic/lonely/ending beats.
Use crossfade as default.

Allowed motion:
still_hold, slow_zoom_in, slow_zoom_out, push_in_center, pan_left, pan_right, pan_up, pan_down, handheld_tension, impact_shake, subtle_shake, pull_back_reveal

Allowed transition:
crossfade, smooth_zoom_fade, dip_to_black, hard_cut, slide_soft, wipe_soft

Allowed vfx:
film_grain, letterbox, rain, dust, fire_embers, cold_mist, dark_smoke, blood_spatter, speed_lines, edge_glow, color_pulse

Allowed color_grade:
neutral, warm_firelight, cold_blue, cold_dusk, dark_jade, blood_amber

Output format:
{
  "version":"effect_plan_v2",
  "fields":["scene","type","mood","motion","intensity","transition","duration","vfx","grade"],
  "items":[
    [1, "mystery_reveal", "mystical", "slow_zoom_in", 0.3, "crossfade", 500, ["film_grain", "dark_smoke"], "dark_jade"],
    [2, "combat_action", "tense", "impact_shake", 0.7, "hard_cut", 0, ["speed_lines", "dust"], "blood_amber"]
  ]
}

Scene input:
{scene_json}
"""
