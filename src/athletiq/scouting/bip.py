"""Binary Integer Programming roster optimization (paper §4.4.3, Eq. 14–18).

    max  sum_{j, i}  Q_{ji} * x_{ji}                                       (Eq. 15)
    s.t. sum_j x_{ji} = n_i       for all i      (formation)               (Eq. 16)
         sum_i x_{ji} <= 1        for all j      (one position per player) (Eq. 17)
         sum_{j, i} F_j * x_{ji} <= F_max         (foreign quota)          (Eq. 18)
         sum_{j, i} V_j * x_{ji} <= B             (budget)                 (Eq. 18)

Also identifies the Squad Gap ``i* = argmax_i Delta_i Q`` — the position whose
marginal fitness upgrade would most improve the objective.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import pulp

FloatArray = npt.NDArray[np.floating]


@dataclass(frozen=True, slots=True)
class SquadOptimizationResult:
    assignments: dict[str, str]  # player_id -> position
    total_score: float
    squad_gap_position: str | None
    squad_gap_delta: float
    budget_used: float
    foreign_count: int


def optimize_squad(
    Q: FloatArray,
    player_ids: list[str],
    positions: list[str],
    formation: dict[str, int],
    foreign_flags: list[bool],
    market_values: list[float],
    budget: float,
    foreign_max: int,
    solver_msg: bool = False,
) -> SquadOptimizationResult:
    """Solve the BIP and identify the Squad Gap.

    Parameters
    ----------
    Q : (N, P) positional fitness matrix from WASPAS.
    player_ids : length-N list of player ids (rows of Q).
    positions : length-P list of position labels (cols of Q).
    formation : {position: n_i} — required count per position.
    foreign_flags : length-N booleans (``F_j``).
    market_values : length-N market values (``V_j``).
    budget : float (``B``).
    foreign_max : int (``F_max``).
    """
    N, P = Q.shape
    if len(player_ids) != N or len(positions) != P:
        raise ValueError("player_ids / positions must match Q shape")
    for pos in formation:
        if pos not in positions:
            raise KeyError(f"formation position '{pos}' not in positions list")

    prob = pulp.LpProblem("athletiq_squad", pulp.LpMaximize)
    x = {
        (j, i): pulp.LpVariable(f"x_{j}_{i}", cat=pulp.LpBinary) for j in range(N) for i in range(P)
    }

    prob += pulp.lpSum(Q[j, i] * x[(j, i)] for j in range(N) for i in range(P))

    # Eq. 16 — formation
    for i, pos in enumerate(positions):
        n_i = int(formation.get(pos, 0))
        prob += pulp.lpSum(x[(j, i)] for j in range(N)) == n_i, f"formation_{pos}"

    # Eq. 17 — one position per player
    for j in range(N):
        prob += pulp.lpSum(x[(j, i)] for i in range(P)) <= 1, f"one_position_{player_ids[j]}"

    # Eq. 18a — foreign quota
    prob += (
        pulp.lpSum(int(foreign_flags[j]) * x[(j, i)] for j in range(N) for i in range(P))
        <= foreign_max,
        "foreign_quota",
    )

    # Eq. 18b — budget
    prob += (
        pulp.lpSum(float(market_values[j]) * x[(j, i)] for j in range(N) for i in range(P))
        <= budget,
        "budget",
    )

    status = prob.solve(pulp.PULP_CBC_CMD(msg=solver_msg))
    if pulp.LpStatus[status] != "Optimal":
        raise RuntimeError(f"BIP did not reach optimal: {pulp.LpStatus[status]}")

    assignments: dict[str, str] = {}
    total = 0.0
    fcount = 0
    bused = 0.0
    per_position_scores: dict[str, list[float]] = {p: [] for p in positions}
    for j in range(N):
        for i in range(P):
            if pulp.value(x[(j, i)]) > 0.5:
                assignments[player_ids[j]] = positions[i]
                total += float(Q[j, i])
                fcount += int(foreign_flags[j])
                bused += float(market_values[j])
                per_position_scores[positions[i]].append(float(Q[j, i]))

    # Squad Gap: position whose lowest assigned Q is farthest from the cohort max at that position
    gap_pos: str | None = None
    gap_delta: float = 0.0
    for i, pos in enumerate(positions):
        if formation.get(pos, 0) == 0 or not per_position_scores[pos]:
            continue
        best = float(Q[:, i].max())
        weakest = min(per_position_scores[pos])
        delta = best - weakest
        if delta > gap_delta:
            gap_delta = delta
            gap_pos = pos

    return SquadOptimizationResult(
        assignments=assignments,
        total_score=float(total),
        squad_gap_position=gap_pos,
        squad_gap_delta=float(gap_delta),
        budget_used=float(bused),
        foreign_count=int(fcount),
    )
