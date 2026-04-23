from __future__ import annotations

from app.models.characters import ChapterCharacterState, CharacterScriptContext, CharacterScriptEntry


class CharacterScriptContextBuilder:
    def build(self, state: ChapterCharacterState) -> CharacterScriptContext:
        active_clusters = {
            cluster.clusterId: cluster
            for cluster in state.clusters
            if cluster.status not in {"ignored", "merged"}
        }
        characters: list[CharacterScriptEntry] = []
        for cluster in active_clusters.values():
            display_label = cluster.displayLabel.strip() or cluster.canonicalName.strip()
            if not display_label:
                continue
            characters.append(
                CharacterScriptEntry(
                    clusterId=cluster.clusterId,
                    canonicalName=cluster.canonicalName.strip(),
                    displayLabel=display_label,
                    lockName=cluster.lockName,
                )
            )
        characters.sort(
            key=lambda item: (
                0 if item.lockName and item.canonicalName.strip() else 1,
                0 if item.canonicalName.strip() else 1,
                item.clusterId,
            )
        )

        panel_character_refs: dict[str, list[str]] = {}
        unknown_panel_ids: list[str] = []
        for ref in state.panelCharacterRefs:
            cluster_ids = [cluster_id for cluster_id in ref.clusterIds if cluster_id in active_clusters]
            if cluster_ids:
                panel_character_refs[ref.panelId] = cluster_ids
            else:
                unknown_panel_ids.append(ref.panelId)

        return CharacterScriptContext(
            chapterId=state.chapterId,
            characters=characters,
            panelCharacterRefs=panel_character_refs,
            unknownPanelIds=unknown_panel_ids,
        )
