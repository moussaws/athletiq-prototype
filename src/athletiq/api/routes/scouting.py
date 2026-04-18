"""Pillar B endpoints: clustering + hybrid KNN similarity retrieval."""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from athletiq.api.state import get_store
from athletiq.insights import describe_player_style, label_archetype
from athletiq.scouting.cluster import fit_kmeans_silhouette, fit_pca
from athletiq.scouting.similarity import knn_similar_players

router = APIRouter()


class SimilarPlayerOut(BaseModel):
    player_id: str
    name: str
    position: str
    nationality: str
    age: int
    market_value_m: float
    similarity: float
    euclidean: float
    cosine_similarity: float


class SimilarityResponse(BaseModel):
    query_player_id: str
    lam: float
    results: list[SimilarPlayerOut]


@router.get("/similar/{player_id}", response_model=SimilarityResponse)
def similar_players(
    player_id: str,
    k: int = Query(default=10, ge=1, le=50),
    lam: float = Query(default=0.5, ge=0.0, le=1.0),
    same_position_only: bool = Query(default=True),
) -> SimilarityResponse:
    store = get_store()
    ids = [p.player_id for p in store.players]
    if player_id not in ids:
        raise HTTPException(status_code=404, detail=f"player {player_id} not found")

    q_idx = ids.index(player_id)
    Xr = store.pca.X_reduced
    query = Xr[q_idx]

    mask = np.ones(len(ids), dtype=bool)
    if same_position_only:
        q_pos = store.players[q_idx].position
        mask = np.array([p.position == q_pos for p in store.players])
    candidate_ids = [ids[i] for i in np.where(mask)[0]]
    candidates = Xr[mask]

    top = knn_similar_players(
        query=query,
        candidates=candidates,
        candidate_ids=candidate_ids,
        k=k + 1,
        lam=lam,
        exclude_ids={player_id},
    )[:k]

    by_id = {p.player_id: p for p in store.players}
    return SimilarityResponse(
        query_player_id=player_id,
        lam=lam,
        results=[
            SimilarPlayerOut(
                player_id=r.player_id,
                name=by_id[r.player_id].name,
                position=by_id[r.player_id].position,
                nationality=by_id[r.player_id].nationality,
                age=by_id[r.player_id].age,
                market_value_m=by_id[r.player_id].market_value_m,
                similarity=r.similarity,
                euclidean=r.euclidean,
                cosine_similarity=r.cosine_similarity,
            )
            for r in top
        ],
    )


class ArchetypeBucket(BaseModel):
    cluster_id: int
    size: int
    members: list[str]
    name: str
    description: str
    key_traits: list[str]


class ArchetypeResponse(BaseModel):
    position: str
    k: int
    silhouette: float
    buckets: list[ArchetypeBucket]


@router.get("/archetypes/{position}", response_model=ArchetypeResponse)
def archetypes_for_position(position: str) -> ArchetypeResponse:
    store = get_store()
    if position not in store.clusters_by_position:
        mask = np.array([p.position == position for p in store.players])
        if mask.sum() < 3:
            raise HTTPException(
                status_code=422, detail=f"not enough players at position '{position}'"
            )
        X_pos = store.X[mask]
        pca = fit_pca(X_pos, variance_target=0.95)
        clust = fit_kmeans_silhouette(pca.X_reduced)
        store.clusters_by_position[position] = (pca, clust)

    _pca, clust = store.clusters_by_position[position]
    players_at_pos = [p for p in store.players if p.position == position]
    ids = np.array([p.player_id for p in players_at_pos])
    buckets: dict[int, list[str]] = {}
    for pid, label in zip(ids.tolist(), clust.labels.tolist(), strict=True):
        buckets.setdefault(int(label), []).append(str(pid))

    # Reference distribution (mean, std) per feature across this position so
    # archetype labeling can reason in z-scores.
    feature_names = list(players_at_pos[0].features.keys())
    feat_matrix = np.array([[p.features[f] for f in feature_names] for p in players_at_pos])
    ref = {
        f: (float(feat_matrix[:, i].mean()), float(feat_matrix[:, i].std()))
        for i, f in enumerate(feature_names)
    }
    id_to_cluster = {
        pid: int(lbl) for pid, lbl in zip(ids.tolist(), clust.labels.tolist(), strict=True)
    }
    # Centroid per cluster in raw feature space (easier to label than PCA space).
    centroids: dict[int, dict[str, float]] = {}
    for cid in sorted(buckets):
        member_rows = [
            [p.features[f] for f in feature_names]
            for p in players_at_pos
            if id_to_cluster[p.player_id] == cid
        ]
        arr = np.array(member_rows)
        centroids[cid] = {f: float(arr[:, i].mean()) for i, f in enumerate(feature_names)}

    bucket_rows: list[ArchetypeBucket] = []
    for c, members in sorted(buckets.items()):
        archetype = label_archetype(position, centroids[c], ref)
        bucket_rows.append(
            ArchetypeBucket(
                cluster_id=c,
                size=len(members),
                members=members,
                name=archetype.name,
                description=archetype.description,
                key_traits=archetype.key_traits,
            )
        )
    return ArchetypeResponse(
        position=position,
        k=clust.k,
        silhouette=clust.silhouette,
        buckets=bucket_rows,
    )


class PlayerStyleResponse(BaseModel):
    player_id: str
    position: str
    style: str
    archetype_name: str
    archetype_description: str
    archetype_key_traits: list[str]


@router.get("/style/{player_id}", response_model=PlayerStyleResponse)
def player_style(player_id: str) -> PlayerStyleResponse:
    """Coach-facing style summary + archetype label for a single player."""
    store = get_store()
    target = next((p for p in store.players if p.player_id == player_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail=f"player {player_id} not found")

    peers = [p for p in store.players if p.position == target.position]
    feature_names = list(target.features.keys())
    arr = np.array([[p.features[f] for f in feature_names] for p in peers])
    ref = {
        f: (float(arr[:, i].mean()), float(arr[:, i].std())) for i, f in enumerate(feature_names)
    }
    style = describe_player_style(target.position, target.features, ref)
    archetype = label_archetype(target.position, target.features, ref)
    return PlayerStyleResponse(
        player_id=player_id,
        position=target.position,
        style=style,
        archetype_name=archetype.name,
        archetype_description=archetype.description,
        archetype_key_traits=archetype.key_traits,
    )
