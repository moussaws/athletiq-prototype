"""Pillar B endpoints: clustering + hybrid KNN similarity retrieval."""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from athletiq.api.state import get_store
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

    pca, clust = store.clusters_by_position[position]
    mask = np.array([p.position == position for p in store.players])
    ids = np.array([p.player_id for p in store.players])[mask]
    buckets: dict[int, list[str]] = {}
    for pid, label in zip(ids.tolist(), clust.labels.tolist(), strict=True):
        buckets.setdefault(int(label), []).append(str(pid))
    return ArchetypeResponse(
        position=position,
        k=clust.k,
        silhouette=clust.silhouette,
        buckets=[
            ArchetypeBucket(cluster_id=c, size=len(members), members=members)
            for c, members in sorted(buckets.items())
        ],
    )
