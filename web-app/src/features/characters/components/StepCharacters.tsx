import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Loader2, RefreshCw, Scissors, UserPlus } from "lucide-react";

import {
  createCharacterCluster,
  mergeCharacterClusters,
  renameCharacterCluster,
  runCharacterPrepass,
  splitCharacterCluster,
  updateCharacterClusterStatus,
  updateCharacterCropMapping,
  updateCharacterPanelMapping,
} from "@/features/characters/api";
import { buildChapterId } from "@/features/characters/chapterId";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useRecapStore } from "@/shared/storage/useRecapStore";
import type { CharacterCandidateAssignment, CharacterCrop } from "@/shared/types";

type DraftNames = Record<string, string>;
type MergeTargets = Record<string, string>;
type SplitSelections = Record<string, boolean>;

export function StepCharacters() {
  const { config, panels, characterState, setCharacterState, setCurrentStep } = useRecapStore();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedPanelId, setSelectedPanelId] = useState<string>("");
  const [draftNames, setDraftNames] = useState<DraftNames>({});
  const [mergeTargets, setMergeTargets] = useState<MergeTargets>({});
  const [newCharacterName, setNewCharacterName] = useState("");
  const [panelOverrideTarget, setPanelOverrideTarget] = useState("");
  const [splitCropSelections, setSplitCropSelections] = useState<SplitSelections>({});
  const [splitPanelSelections, setSplitPanelSelections] = useState<SplitSelections>({});
  const [splitName, setSplitName] = useState("");

  const chapterId = useMemo(() => buildChapterId(panels), [panels]);
  const panelById = useMemo(() => new Map(panels.map((panel) => [panel.id, panel])), [panels]);
  const refsByPanelId = useMemo(
    () => new Map((characterState?.panelCharacterRefs || []).map((item) => [item.panelId, item])),
    [characterState]
  );
  const panelRefsByClusterId = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const ref of characterState?.panelCharacterRefs || []) {
      for (const clusterId of ref.clusterIds || []) {
        const current = map.get(clusterId) || [];
        current.push(ref.panelId);
        map.set(clusterId, current);
      }
    }
    return map;
  }, [characterState?.panelCharacterRefs]);
  const cropsByPanelId = useMemo(() => {
    const map = new Map<string, CharacterCrop[]>();
    for (const crop of characterState?.crops || []) {
      const current = map.get(crop.panelId) || [];
      current.push(crop);
      map.set(crop.panelId, current);
    }
    return map;
  }, [characterState?.crops]);
  const candidatesByCropId = useMemo(() => {
    const map = new Map<string, CharacterCandidateAssignment[]>();
    for (const assignment of characterState?.candidateAssignments || []) {
      const current = map.get(assignment.cropId) || [];
      current.push(assignment);
      map.set(assignment.cropId, current);
    }
    for (const assignments of map.values()) {
      assignments.sort((left, right) => left.rank - right.rank);
    }
    return map;
  }, [characterState?.candidateAssignments]);
  const cropById = useMemo(() => new Map((characterState?.crops || []).map((crop) => [crop.cropId, crop])), [characterState?.crops]);
  const selectedSplitCropIds = useMemo(
    () => Object.entries(splitCropSelections).filter(([, selected]) => selected).map(([cropId]) => cropId),
    [splitCropSelections]
  );
  const selectedSplitPanelIds = useMemo(
    () => Object.entries(splitPanelSelections).filter(([, selected]) => selected).map(([panelId]) => panelId),
    [splitPanelSelections]
  );
  const activeClusters = useMemo(
    () => (characterState?.clusters || []).filter((cluster) => cluster.status !== "merged" && cluster.status !== "ignored"),
    [characterState?.clusters]
  );
  const possibleWrongMergeClusters = useMemo(
    () => activeClusters.filter((cluster) => (cluster.reviewFlags || []).includes("possible_merge")),
    [activeClusters]
  );
  const unresolvedPanels = characterState?.unresolvedPanelIds || [];
  const selectedPanel = selectedPanelId ? panelById.get(selectedPanelId) || null : panels[0] || null;
  const selectedRef = selectedPanel ? refsByPanelId.get(selectedPanel.id) : undefined;
  const selectedPanelCrops = selectedPanel ? cropsByPanelId.get(selectedPanel.id) || [] : [];

  useEffect(() => {
    if (!selectedPanelId && panels[0]) {
      setSelectedPanelId(panels[0].id);
    }
  }, [panels, selectedPanelId]);

  useEffect(() => {
    if (!characterState) return;
    setDraftNames(
      Object.fromEntries(
        (characterState.clusters || []).map((cluster) => [
          cluster.clusterId,
          cluster.canonicalName || cluster.displayLabel || "",
        ])
      )
    );
  }, [characterState]);

  useEffect(() => {
    if (panels.length === 0 || !config.apiBaseUrl) return;
    if (characterState?.chapterId === chapterId) return;

    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const state = await runCharacterPrepass(config.apiBaseUrl, chapterId, panels);
        if (!cancelled) {
          setCharacterState(state);
        }
      } catch (prepassError) {
        if (!cancelled) {
          setError(prepassError instanceof Error ? prepassError.message : "Character prepass failed.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, [chapterId, characterState?.chapterId, config.apiBaseUrl, panels, setCharacterState]);

  const applyState = (state: typeof characterState) => {
    if (!state) return;
    setCharacterState(state);
    setError(null);
  };

  const requireApiBaseUrl = () => {
    if (!config.apiBaseUrl) {
      throw new Error("Missing backend API base URL. Open Settings and enter a valid backend URL.");
    }
  };

  const rerunPrepass = async () => {
    try {
      requireApiBaseUrl();
      setLoading(true);
      const state = await runCharacterPrepass(config.apiBaseUrl, chapterId, panels, { force: true });
      applyState(state);
    } catch (prepassError) {
      setError(prepassError instanceof Error ? prepassError.message : "Character prepass failed.");
    } finally {
      setLoading(false);
    }
  };

  const saveRename = async (clusterId: string, lockName: boolean) => {
    try {
      requireApiBaseUrl();
      setSaving(true);
      const canonicalName = draftNames[clusterId]?.trim() || "";
      const state = await renameCharacterCluster(config.apiBaseUrl, {
        chapterId,
        clusterId,
        canonicalName,
        lockName,
      });
      applyState(state);
    } catch (renameError) {
      setError(renameError instanceof Error ? renameError.message : "Unable to save character name.");
    } finally {
      setSaving(false);
    }
  };

  const createManualCharacter = async () => {
    const canonicalName = newCharacterName.trim();
    if (!canonicalName) return;
    try {
      requireApiBaseUrl();
      setSaving(true);
      const preferredCrop = [...selectedPanelCrops]
        .sort((left, right) => right.qualityScore - left.qualityScore)
        .find((crop) => crop.assignmentState !== "auto_confirmed" && crop.assignmentState !== "manual");
      const state = await createCharacterCluster(config.apiBaseUrl, {
        chapterId,
        canonicalName,
        displayLabel: canonicalName,
        lockName: true,
        cropIds: preferredCrop ? [preferredCrop.cropId] : [],
        panelIds: selectedPanel ? [selectedPanel.id] : [],
      });
      applyState(state);
      setNewCharacterName("");
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Unable to create character.");
    } finally {
      setSaving(false);
    }
  };

  const applyPanelOverride = async () => {
    if (!selectedPanel) return;
    try {
      requireApiBaseUrl();
      setSaving(true);
      const clusterIds = panelOverrideTarget ? [panelOverrideTarget] : [];
      const state = await updateCharacterPanelMapping(config.apiBaseUrl, {
        chapterId,
        panelId: selectedPanel.id,
        clusterIds,
      });
      applyState(state);
    } catch (mappingError) {
      setError(mappingError instanceof Error ? mappingError.message : "Unable to update panel mapping.");
    } finally {
      setSaving(false);
    }
  };

  const updateCropAssignment = async (cropId: string, clusterId?: string | null) => {
    try {
      requireApiBaseUrl();
      setSaving(true);
      const state = await updateCharacterCropMapping(config.apiBaseUrl, {
        chapterId,
        cropId,
        clusterId: clusterId || null,
      });
      applyState(state);
    } catch (cropError) {
      setError(cropError instanceof Error ? cropError.message : "Unable to update crop assignment.");
    } finally {
      setSaving(false);
    }
  };

  const markClusterStatus = async (clusterId: string, status: "draft" | "unknown" | "ignored") => {
    try {
      requireApiBaseUrl();
      setSaving(true);
      const state = await updateCharacterClusterStatus(config.apiBaseUrl, {
        chapterId,
        clusterId,
        status,
      });
      applyState(state);
    } catch (statusError) {
      setError(statusError instanceof Error ? statusError.message : "Unable to update character status.");
    } finally {
      setSaving(false);
    }
  };

  const mergeCluster = async (sourceClusterId: string) => {
    const targetClusterId = mergeTargets[sourceClusterId];
    if (!targetClusterId || targetClusterId === sourceClusterId) return;
    try {
      requireApiBaseUrl();
      setSaving(true);
      const state = await mergeCharacterClusters(config.apiBaseUrl, {
        chapterId,
        sourceClusterId,
        targetClusterId,
      });
      applyState(state);
    } catch (mergeError) {
      setError(mergeError instanceof Error ? mergeError.message : "Unable to merge characters.");
    } finally {
      setSaving(false);
    }
  };

  const toggleSplitCrop = (cropId: string) => {
    setSplitCropSelections((current) => ({ ...current, [cropId]: !current[cropId] }));
  };

  const toggleSplitPanel = (panelId: string) => {
    setSplitPanelSelections((current) => ({ ...current, [panelId]: !current[panelId] }));
  };

  const splitSelectedFromCluster = async (sourceClusterId: string) => {
    const cropIds = selectedSplitCropIds.filter((cropId) => cropById.get(cropId)?.assignedClusterId === sourceClusterId);
    const panelIds = selectedSplitPanelIds.filter((panelId) => {
      const ref = refsByPanelId.get(panelId);
      return ref?.clusterIds.includes(sourceClusterId) || (cropsByPanelId.get(panelId) || []).some((crop) => crop.assignedClusterId === sourceClusterId);
    });
    if (cropIds.length === 0 && panelIds.length === 0) {
      setError("Select at least one crop or panel from this cluster before splitting.");
      return;
    }
    try {
      requireApiBaseUrl();
      setSaving(true);
      const state = await splitCharacterCluster(config.apiBaseUrl, {
        chapterId,
        sourceClusterId,
        cropIds,
        panelIds,
        canonicalName: splitName.trim(),
      });
      applyState(state);
      setSplitCropSelections({});
      setSplitPanelSelections({});
      setSplitName("");
    } catch (splitError) {
      setError(splitError instanceof Error ? splitError.message : "Unable to split character.");
    } finally {
      setSaving(false);
    }
  };

  if (panels.length === 0) {
    return (
      <Card className="glass rounded-3xl border-white/10 bg-white/5 p-8 text-white/80">
        Extract hoac import panel truoc khi review character mapping.
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between rounded-3xl border border-white/10 bg-white/5 p-6">
        <div className="space-y-1">
          <h2 className="text-3xl font-bold tracking-tight text-white">Character Review</h2>
          <p className="text-sm text-white/60">
            Prepass da chuyen sang crop-level identity. Script chi nhan panel ref da confirm, con case suggested se nam trong queue review.
          </p>
        </div>
        <div className="flex gap-3">
          <Button
            variant="outline"
            onClick={() => setCurrentStep("extract")}
            className="border-white/15 bg-white/5 px-6 font-bold text-white hover:bg-white/10"
          >
            <ChevronLeft className="mr-2 h-4 w-4" /> Quay lai
          </Button>
          <Button
            variant="outline"
            onClick={rerunPrepass}
            disabled={loading || saving}
            className="border-primary/30 bg-primary/10 px-6 font-bold text-primary hover:bg-primary/15"
          >
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
            Re-run prepass
          </Button>
          <Button onClick={() => setCurrentStep("script")} className="px-8 font-bold" disabled={loading}>
            Sang Script <ChevronRight className="ml-2 h-4 w-4" />
          </Button>
        </div>
      </div>

      {(error || loading) && (
        <Card className="rounded-3xl border border-white/10 bg-black/20 p-4 text-sm text-white/80">
          {loading ? "Dang chay character prepass..." : error}
        </Card>
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="rounded-3xl border border-white/10 bg-black/20 p-5">
          <p className="text-xs uppercase tracking-[0.2em] text-white/40">Clusters</p>
          <p className="mt-2 text-3xl font-bold text-white">{activeClusters.length}</p>
          <p className="mt-1 text-sm text-white/55">reviewable identities in current chapter</p>
        </Card>
        <Card className="rounded-3xl border border-white/10 bg-black/20 p-5">
          <p className="text-xs uppercase tracking-[0.2em] text-white/40">Possible Wrong Merge</p>
          <p className="mt-2 text-3xl font-bold text-white">{possibleWrongMergeClusters.length}</p>
          <p className="mt-1 text-sm text-white/55">clusters with centroid overlap warning</p>
        </Card>
        <Card className="rounded-3xl border border-white/10 bg-black/20 p-5">
          <p className="text-xs uppercase tracking-[0.2em] text-white/40">Near-Threshold Unknown</p>
          <p className="mt-2 text-3xl font-bold text-white">{unresolvedPanels.length}</p>
          <p className="mt-1 text-sm text-white/55">panels that still need crop review</p>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-6">
          <Card className="glass rounded-3xl border-white/10 bg-white/5 p-6">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-white">Character List</h3>
                <p className="text-sm text-white/50">
                  {activeClusters.length} clusters, {characterState?.needsReview ? "can review" : "ready"}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Input
                  value={splitName}
                  onChange={(event) => setSplitName(event.target.value)}
                  placeholder="Ten character split"
                  className="h-10 w-48 rounded-xl border-white/15 bg-white/10 text-white"
                />
                <Input
                  value={newCharacterName}
                  onChange={(event) => setNewCharacterName(event.target.value)}
                  placeholder="Them character thu cong"
                  className="h-10 w-56 rounded-xl border-white/15 bg-white/10 text-white"
                />
                <Button onClick={createManualCharacter} disabled={saving || !newCharacterName.trim()} className="font-bold">
                  <UserPlus className="mr-2 h-4 w-4" /> Add
                </Button>
              </div>
            </div>

            <div className="space-y-4">
              {activeClusters.length === 0 && (
                <div className="rounded-2xl border border-dashed border-white/10 bg-black/20 p-5 text-sm text-white/60">
                  Chua co cluster nao duoc auto-group. Hay tao character thu cong hoac gan crop trong crop inspector.
                </div>
              )}

              {activeClusters.map((cluster) => {
                const clusterPanelIds = [
                  ...new Set([
                    ...(panelRefsByClusterId.get(cluster.clusterId) || []),
                    ...(cluster.anchorPanelIds || []),
                    ...(cluster.samplePanelIds || []),
                  ]),
                ].sort((left, right) => (panelById.get(left)?.order ?? 0) - (panelById.get(right)?.order ?? 0));
                const clusterPanels = clusterPanelIds
                  .map((panelId) => panelById.get(panelId))
                  .filter((panel): panel is NonNullable<typeof panel> => !!panel);
                const splitCropCount = selectedSplitCropIds.filter((cropId) => cropById.get(cropId)?.assignedClusterId === cluster.clusterId).length;
                const splitPanelCount = selectedSplitPanelIds.filter((panelId) => {
                  const ref = refsByPanelId.get(panelId);
                  return ref?.clusterIds.includes(cluster.clusterId) || (cropsByPanelId.get(panelId) || []).some((crop) => crop.assignedClusterId === cluster.clusterId);
                }).length;
                return (
                  <Card key={cluster.clusterId} className="rounded-2xl border border-white/10 bg-black/20 p-5">
                    <div className="grid grid-cols-1 gap-5">
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-base font-semibold text-white">
                              {cluster.canonicalName || cluster.displayLabel || cluster.clusterId}
                            </p>
                            <p className="text-xs uppercase tracking-wide text-white/40">
                              {cluster.clusterId} • {cluster.occurrenceCount} panels • confidence {Math.round(cluster.confidenceScore * 100)}%
                            </p>
                          </div>
                          <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[10px] font-bold uppercase tracking-wide text-white/60">
                            {cluster.status}
                          </span>
                        </div>

                        <div className="flex flex-wrap gap-2">
                          {(cluster.reviewFlags || []).map((flag) => (
                            <span
                              key={flag}
                              className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[10px] uppercase tracking-wide text-white/55"
                            >
                              {flag}
                            </span>
                          ))}
                        </div>

                        <div className="space-y-2">
                          <Label className="text-[10px] font-semibold uppercase tracking-wide text-white/70">Canonical Name</Label>
                          <Input
                            value={draftNames[cluster.clusterId] ?? ""}
                            onChange={(event) =>
                              setDraftNames((current) => ({
                                ...current,
                                [cluster.clusterId]: event.target.value,
                              }))
                            }
                            className="h-11 rounded-xl border-white/15 bg-white/10 text-white"
                          />
                        </div>

                        <div className="flex flex-wrap gap-2">
                          <Button size="sm" onClick={() => void saveRename(cluster.clusterId, true)} disabled={saving} className="font-bold">
                            Save + Lock
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => void saveRename(cluster.clusterId, false)}
                            disabled={saving}
                            className="border-white/15 bg-white/5 text-white hover:bg-white/10"
                          >
                            Save Draft
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => void splitSelectedFromCluster(cluster.clusterId)}
                            disabled={saving || (splitCropCount === 0 && splitPanelCount === 0)}
                            className="border-amber-300/25 bg-amber-400/10 text-amber-100 hover:bg-amber-400/15"
                          >
                            <Scissors className="mr-2 h-4 w-4" />
                            Split {splitCropCount + splitPanelCount || ""}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => void markClusterStatus(cluster.clusterId, "unknown")}
                            disabled={saving}
                            className="border-white/15 bg-white/5 text-white hover:bg-white/10"
                          >
                            Mark Unknown
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => void markClusterStatus(cluster.clusterId, "ignored")}
                            disabled={saving}
                            className="border-white/15 bg-white/5 text-white hover:bg-white/10"
                          >
                            Ignore
                          </Button>
                        </div>
                      </div>

                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <p className="text-[10px] font-semibold uppercase tracking-wide text-white/55">
                            Panels in this character
                          </p>
                          <span className="text-xs text-white/45">
                            showing {clusterPanels.length} / {cluster.occurrenceCount}
                          </span>
                        </div>
                        {clusterPanels.length === 0 ? (
                          <div className="rounded-2xl border border-dashed border-white/10 bg-black/20 p-4 text-sm text-white/55">
                            No panel references are available for this cluster yet. Re-run prepass to rebuild character references.
                          </div>
                        ) : (
                          <div className="grid grid-cols-4 gap-2 sm:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10">
                            {clusterPanels.map((panel) => {
                              const isSelected = selectedPanel?.id === panel.id;
                              const isSplitSelected = !!splitPanelSelections[panel.id];
                              return (
                                <button
                                  key={panel.id}
                                  type="button"
                                  onClick={() => setSelectedPanelId(panel.id)}
                                  className={`group overflow-hidden rounded-xl border bg-black/30 text-left transition-colors ${
                                    isSplitSelected
                                      ? "border-amber-300/70 ring-2 ring-amber-300/20"
                                      : isSelected
                                        ? "border-primary/70 ring-2 ring-primary/25"
                                        : "border-white/10 hover:border-white/30"
                                  }`}
                                >
                                  <div className="relative h-20 w-full overflow-hidden">
                                    <img
                                      src={panel.thumbnail || panel.base64}
                                      alt={`Panel ${panel.order + 1}`}
                                      className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-110"
                                    />
                                    <span className="absolute bottom-1 left-1 rounded-md bg-black/70 px-1.5 py-0.5 text-[10px] font-bold text-white/85">
                                      {panel.order + 1}
                                    </span>
                                    {isSplitSelected && (
                                      <span className="absolute right-1 top-1 rounded-md bg-amber-400/85 px-1.5 py-0.5 text-[9px] font-bold uppercase text-black">
                                        split
                                      </span>
                                    )}
                                  </div>
                                </button>
                              );
                            })}
                          </div>
                        )}

                        {(cluster.anchorCropIds || []).length > 0 && (
                          <div className="space-y-2">
                            <p className="text-[10px] font-semibold uppercase tracking-wide text-white/45">
                              Representative crops
                            </p>
                            <div className="grid grid-cols-4 gap-2 sm:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10">
                              {(cluster.anchorCropIds || [])
                                .map((cropId) => cropById.get(cropId))
                                .filter((crop): crop is NonNullable<typeof crop> => !!crop)
                                .slice(0, 10)
                                .map((crop) => (
                                  <button
                                    key={crop.cropId}
                                    type="button"
                                    onClick={() => setSelectedPanelId(crop.panelId)}
                                    className={`relative overflow-hidden rounded-xl border bg-black/30 ${
                                      splitCropSelections[crop.cropId] ? "border-amber-300/70 ring-2 ring-amber-300/20" : "border-white/10"
                                    }`}
                                  >
                                    <img src={crop.previewImage} alt={crop.cropId} className="h-20 w-20 object-cover" />
                                    <span className="absolute bottom-1 left-1 rounded bg-black/70 px-1.5 py-0.5 text-[9px] uppercase text-white/80">
                                      {crop.kind}
                                    </span>
                                  </button>
                                ))}
                            </div>
                          </div>
                        )}

                        {activeClusters.length > 1 && (
                          <div className="flex items-center gap-2">
                            <select
                              value={mergeTargets[cluster.clusterId] || ""}
                              onChange={(event) =>
                                setMergeTargets((current) => ({
                                  ...current,
                                  [cluster.clusterId]: event.target.value,
                                }))
                              }
                              className="h-10 min-w-44 rounded-xl border border-white/15 bg-white/10 px-3 text-sm text-white"
                            >
                              <option value="">Merge vao...</option>
                              {activeClusters
                                .filter((candidate) => candidate.clusterId !== cluster.clusterId)
                                .map((candidate) => (
                                  <option key={candidate.clusterId} value={candidate.clusterId}>
                                    {candidate.canonicalName || candidate.displayLabel || candidate.clusterId}
                                  </option>
                                ))}
                            </select>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => void mergeCluster(cluster.clusterId)}
                              disabled={saving || !mergeTargets[cluster.clusterId]}
                              className="border-white/15 bg-white/5 text-white hover:bg-white/10"
                            >
                              Merge
                            </Button>
                          </div>
                        )}
                      </div>
                    </div>
                  </Card>
                );
              })}
            </div>
          </Card>

          {selectedPanel && (
            <Card className="glass rounded-3xl border-white/10 bg-white/5 p-6">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-bold text-white">Selected Panel</h3>
                  <p className="text-sm text-white/50">
                    Panel {selectedPanel.order + 1} dang duoc chon de review va gan character.
                  </p>
                </div>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[10px] font-bold uppercase tracking-wide text-white/60">
                  {selectedPanelCrops.length} crops
                </span>
              </div>

              <div className="overflow-hidden rounded-2xl border border-white/10 bg-black/30">
                <img
                  src={selectedPanel.base64 || selectedPanel.thumbnail}
                  alt={selectedPanel.id}
                  className="max-h-[26rem] w-full object-contain"
                />
              </div>
            </Card>
          )}
        </div>

        <div className="space-y-6">
          <Card className="glass rounded-3xl border-white/10 bg-white/5 p-6">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-white">Panel Inspector</h3>
                <p className="text-sm text-white/50">
                  Quick override o cap panel va crop-level assignment cho tung detection.
                </p>
              </div>
              <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[10px] font-bold uppercase tracking-wide text-white/60">
                {selectedPanel ? `Panel ${selectedPanel.order + 1}` : "No panel"}
              </span>
            </div>

            <div className="grid grid-cols-3 gap-3">
              {panels.map((panel) => {
                const isActive = panel.id === selectedPanel?.id;
                const assignedCount = refsByPanelId.get(panel.id)?.clusterIds.length || 0;
                const panelCropCount = cropsByPanelId.get(panel.id)?.length || 0;
                const unresolved = unresolvedPanels.includes(panel.id);
                return (
                  <button
                    key={panel.id}
                    type="button"
                    onClick={() => setSelectedPanelId(panel.id)}
                    className={`overflow-hidden rounded-2xl border ${isActive ? "border-primary/60" : "border-white/10"} bg-black/30 text-left`}
                  >
                    <img src={panel.thumbnail || panel.base64} alt={panel.id} className="h-24 w-full object-cover" />
                    <div className="px-3 py-2 text-xs text-white/70">
                      Panel {panel.order + 1} • {panelCropCount} crops • {assignedCount} refs {unresolved ? "• review" : ""}
                    </div>
                  </button>
                );
              })}
            </div>

            {selectedPanel && (
              <div className="mt-5 space-y-4 rounded-2xl border border-white/10 bg-black/20 p-4">
                <div className="space-y-2">
                  <Label className="text-[10px] font-semibold uppercase tracking-wide text-white/65">Quick Panel Override</Label>
                  <div className="flex flex-wrap gap-2">
                    <select
                      value={panelOverrideTarget}
                      onChange={(event) => setPanelOverrideTarget(event.target.value)}
                      className="h-10 min-w-44 rounded-xl border border-white/15 bg-white/10 px-3 text-sm text-white"
                    >
                      <option value="">Set unknown</option>
                      {activeClusters.map((cluster) => (
                        <option key={cluster.clusterId} value={cluster.clusterId}>
                          {cluster.canonicalName || cluster.displayLabel || cluster.clusterId}
                        </option>
                      ))}
                    </select>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => void applyPanelOverride()}
                      disabled={saving}
                      className="border-white/15 bg-white/5 text-white hover:bg-white/10"
                    >
                      Apply
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => toggleSplitPanel(selectedPanel.id)}
                      className={
                        splitPanelSelections[selectedPanel.id]
                          ? "border-amber-300/50 bg-amber-400/15 text-amber-100 hover:bg-amber-400/20"
                          : "border-white/15 bg-white/5 text-white hover:bg-white/10"
                      }
                    >
                      <Scissors className="mr-2 h-4 w-4" />
                      {splitPanelSelections[selectedPanel.id] ? "Panel selected for split" : "Select panel for split"}
                    </Button>
                  </div>
                  <p className="text-xs text-white/45">
                    Override nhanh cho Script. Neu can chinh dung crop thi su dung crop inspector ben duoi.
                  </p>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold text-white">Detected Crops</p>
                    <span className="text-xs text-white/45">
                      panel ref: {(selectedRef?.clusterIds || []).join(", ") || "unknown"}
                    </span>
                  </div>

                  {selectedPanelCrops.length === 0 && (
                    <div className="rounded-2xl border border-dashed border-white/10 bg-black/20 p-4 text-sm text-white/55">
                      Panel nay chua co detection crop du chat luong. Neu can, tao manual character va dung panel override.
                    </div>
                  )}

                  <div className="space-y-3">
                    {selectedPanelCrops.map((crop) => {
                      const cropCandidates = candidatesByCropId.get(crop.cropId) || [];
                      return (
                        <div key={crop.cropId} className="rounded-2xl border border-white/10 bg-black/30 p-4">
                          <div className="flex gap-4">
                            <button
                              type="button"
                              onClick={() => toggleSplitCrop(crop.cropId)}
                              className={`relative h-24 w-24 shrink-0 overflow-hidden rounded-xl border ${
                                splitCropSelections[crop.cropId] ? "border-amber-300/70 ring-2 ring-amber-300/20" : "border-white/10"
                              }`}
                            >
                              <img src={crop.previewImage} alt={crop.cropId} className="h-full w-full object-cover" />
                              <span className="absolute right-1 top-1 rounded bg-black/70 px-1.5 py-0.5 text-[9px] font-bold uppercase text-white/80">
                                split
                              </span>
                            </button>
                            <div className="min-w-0 flex-1 space-y-2">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="text-sm font-semibold text-white">{crop.cropId.split("::").pop()}</span>
                                <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] uppercase tracking-wide text-white/55">
                                  {crop.kind}
                                </span>
                                <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] uppercase tracking-wide text-white/55">
                                  {crop.qualityBucket}
                                </span>
                                <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] uppercase tracking-wide text-white/55">
                                  {crop.assignmentState}
                                </span>
                                <span className="text-xs text-white/45">
                                  quality {Math.round(crop.qualityScore * 100)}% • detect {Math.round(crop.detectionScore * 100)}%
                                </span>
                              </div>
                              <p className="text-xs text-white/45">
                                bbox [{crop.bbox.join(", ")}] • assigned {crop.assignedClusterId || "unknown"} • {crop.detectorSource}
                                {crop.detectorModel ? ` / ${crop.detectorModel}` : ""}
                              </p>
                              <div className="flex flex-wrap gap-2">
                                {cropCandidates.length === 0 && (
                                  <span className="text-xs text-white/45">No strong cluster candidate.</span>
                                )}
                                {cropCandidates.map((candidate) => (
                                  <Button
                                    key={`${crop.cropId}-${candidate.clusterId}-${candidate.rank}`}
                                    size="sm"
                                    variant={crop.assignedClusterId === candidate.clusterId ? "default" : "outline"}
                                    onClick={() => void updateCropAssignment(crop.cropId, candidate.clusterId)}
                                    disabled={saving}
                                    className={crop.assignedClusterId === candidate.clusterId ? "font-bold" : "border-white/15 bg-white/5 text-white hover:bg-white/10"}
                                  >
                                    {activeClusters.find((cluster) => cluster.clusterId === candidate.clusterId)?.canonicalName ||
                                      activeClusters.find((cluster) => cluster.clusterId === candidate.clusterId)?.displayLabel ||
                                      candidate.clusterId}
                                    {" "}
                                    {Math.round(candidate.score * 100)}%
                                  </Button>
                                ))}
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => void updateCropAssignment(crop.cropId, null)}
                                  disabled={saving}
                                  className="border-white/15 bg-white/5 text-white hover:bg-white/10"
                                >
                                  Clear
                                </Button>
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
