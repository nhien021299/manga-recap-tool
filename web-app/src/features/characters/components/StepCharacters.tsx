import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Loader2, RefreshCw, UserPlus } from "lucide-react";

import {
  createCharacterCluster,
  mergeCharacterClusters,
  renameCharacterCluster,
  runCharacterPrepass,
  updateCharacterClusterStatus,
  updateCharacterPanelMapping,
} from "@/features/characters/api";
import { buildChapterId } from "@/features/characters/chapterId";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useRecapStore } from "@/shared/storage/useRecapStore";

type DraftNames = Record<string, string>;
type MergeTargets = Record<string, string>;

export function StepCharacters() {
  const {
    config,
    panels,
    characterState,
    setCharacterState,
    setCurrentStep,
  } = useRecapStore();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedPanelId, setSelectedPanelId] = useState<string>("");
  const [draftNames, setDraftNames] = useState<DraftNames>({});
  const [mergeTargets, setMergeTargets] = useState<MergeTargets>({});
  const [newCharacterName, setNewCharacterName] = useState("");

  const chapterId = useMemo(() => buildChapterId(panels), [panels]);
  const panelById = useMemo(() => new Map(panels.map((panel) => [panel.id, panel])), [panels]);
  const refsByPanelId = useMemo(
    () => new Map((characterState?.panelCharacterRefs || []).map((item) => [item.panelId, item])),
    [characterState]
  );
  const activeClusters = useMemo(
    () => (characterState?.clusters || []).filter((cluster) => cluster.status !== "merged" && cluster.status !== "ignored"),
    [characterState]
  );
  const selectedPanel = selectedPanelId ? panelById.get(selectedPanelId) || null : panels[0] || null;
  const selectedRef = selectedPanel ? refsByPanelId.get(selectedPanel.id) : undefined;

  useEffect(() => {
    if (!selectedPanelId && panels[0]) {
      setSelectedPanelId(panels[0].id);
    }
  }, [panels, selectedPanelId]);

  useEffect(() => {
    if (!characterState) return;
    setDraftNames(
      Object.fromEntries(
        characterState.clusters.map((cluster) => [
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
      const state = await createCharacterCluster(config.apiBaseUrl, {
        chapterId,
        canonicalName,
        displayLabel: canonicalName,
        lockName: true,
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

  const updateSelectedPanelAssignments = async (clusterId: string) => {
    if (!selectedPanel) return;
    try {
      requireApiBaseUrl();
      setSaving(true);
      const currentIds = new Set(selectedRef?.clusterIds || []);
      if (currentIds.has(clusterId)) currentIds.delete(clusterId);
      else currentIds.add(clusterId);
      const state = await updateCharacterPanelMapping(config.apiBaseUrl, {
        chapterId,
        panelId: selectedPanel.id,
        clusterIds: [...currentIds],
      });
      applyState(state);
    } catch (mappingError) {
      setError(mappingError instanceof Error ? mappingError.message : "Unable to update panel mapping.");
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

  if (panels.length === 0) {
    return (
      <Card className="glass rounded-3xl border-white/10 bg-white/5 p-8 text-white/80">
        Extract hoặc import panel trước khi review character mapping.
      </Card>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex items-center justify-between rounded-3xl border border-white/10 bg-white/5 p-6">
        <div className="space-y-1">
          <h2 className="text-3xl font-bold tracking-tight text-white">Character Review</h2>
          <p className="text-sm text-white/60">
            Prepass đang chạy theo hướng bảo thủ: chỉ auto-group khi rất chắc, còn lại để manual mapping nhằm tránh merge nhầm.
          </p>
        </div>
        <div className="flex gap-3">
          <Button
            variant="outline"
            onClick={() => setCurrentStep("extract")}
            className="border-white/15 bg-white/5 px-6 font-bold text-white hover:bg-white/10"
          >
            <ChevronLeft className="mr-2 h-4 w-4" /> Quay lại
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

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="space-y-6">
          <Card className="glass rounded-3xl border-white/10 bg-white/5 p-6">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-white">Character List</h3>
                <p className="text-sm text-white/50">
                  {characterState?.clusters.length || 0} clusters, {characterState?.needsReview ? "can review" : "ready"}
                </p>
              </div>
              <div className="flex items-center gap-2">
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
                  Chua co cluster nao duoc auto-group. Hay tao character thu cong va gan panel trong panel inspector.
                </div>
              )}

              {activeClusters.map((cluster) => (
                <Card key={cluster.clusterId} className="rounded-2xl border border-white/10 bg-black/20 p-5">
                  <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_auto]">
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
                      <div className="grid grid-cols-4 gap-2">
                        {cluster.anchorPanelIds.slice(0, 4).map((panelId) => {
                          const panel = panelById.get(panelId);
                          if (!panel) return null;
                          return (
                            <button
                              key={panelId}
                              onClick={() => setSelectedPanelId(panelId)}
                              className="overflow-hidden rounded-xl border border-white/10 bg-black/30"
                              type="button"
                            >
                              <img src={panel.thumbnail || panel.base64} alt={panelId} className="h-20 w-20 object-cover" />
                            </button>
                          );
                        })}
                      </div>

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
              ))}
            </div>
          </Card>
        </div>

        <div className="space-y-6">
          <Card className="glass rounded-3xl border-white/10 bg-white/5 p-6">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-white">Panel Inspector</h3>
                <p className="text-sm text-white/50">
                  Gan character cho tung panel. Manual mapping se override auto suggestion o Script step.
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
                return (
                  <button
                    key={panel.id}
                    type="button"
                    onClick={() => setSelectedPanelId(panel.id)}
                    className={`overflow-hidden rounded-2xl border ${isActive ? "border-primary/60" : "border-white/10"} bg-black/30 text-left`}
                  >
                    <img src={panel.thumbnail || panel.base64} alt={panel.id} className="h-24 w-full object-cover" />
                    <div className="px-3 py-2 text-xs text-white/70">
                      Panel {panel.order + 1} • {assignedCount} refs
                    </div>
                  </button>
                );
              })}
            </div>

            {selectedPanel && (
              <div className="mt-5 space-y-3 rounded-2xl border border-white/10 bg-black/20 p-4">
                <div className="overflow-hidden rounded-2xl border border-white/10 bg-black/30">
                  <img src={selectedPanel.base64 || selectedPanel.thumbnail} alt={selectedPanel.id} className="max-h-80 w-full object-contain" />
                </div>
                <div className="flex flex-wrap gap-2">
                  {activeClusters.map((cluster) => {
                    const assigned = !!selectedRef?.clusterIds.includes(cluster.clusterId);
                    return (
                      <Button
                        key={cluster.clusterId}
                        size="sm"
                        variant={assigned ? "default" : "outline"}
                        onClick={() => void updateSelectedPanelAssignments(cluster.clusterId)}
                        disabled={saving}
                        className={assigned ? "font-bold" : "border-white/15 bg-white/5 text-white hover:bg-white/10"}
                      >
                        {cluster.canonicalName || cluster.displayLabel || cluster.clusterId}
                      </Button>
                    );
                  })}
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
