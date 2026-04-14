
from __future__ import annotations

import chess

# The stored score is the true minimax value at the cached depth.
EXACT: int = 0

# The stored score is a lower bound (the search failed high, score >= beta)
LOWER: int = 1

# The stored score is an upper bound (the search failed low, score <= alpha)
UPPER: int = 2

# In memory hash table mapping positions to search results to speed up move generation
class TranspositionTable:
    def __init__(self, size_mb: int = 16) -> None:
        self._table: dict = {}
        self._max_entries: int = self._entries_for_mb(size_mb)

    def resize(self, size_mb: int) -> None:
        self._max_entries = self._entries_for_mb(size_mb)

    def clear(self) -> None:
        self._table.clear()

    def evict_if_full(self) -> None:
        if len(self._table) > self._max_entries:
            self._table.clear()

    def store(self, board: chess.Board, depth: int, score: int, flag: int, best_move_uci: str | None) -> None:
        key = self._key(board)
        existing = self._table.get(key)
        if existing is not None and depth < existing[0]:
            return
        self._table[key] = (depth, flag, score, best_move_uci)

    def probe(self, board: chess.Board, depth: int, alpha: int, beta: int) -> tuple[bool, int | None, str | None, int, int]:
        key = self._key(board)
        entry = self._table.get(key)
        if entry is None:
            return False, None, None, alpha, beta

        e_depth, e_flag, e_score, e_bm = entry

        if e_depth >= depth:
            if e_flag == EXACT:
                return True, e_score, e_bm, alpha, beta
            if e_flag == LOWER:
                if e_score >= beta:
                    return True, e_score, e_bm, alpha, beta
                alpha = max(alpha, e_score)
            elif e_flag == UPPER:
                if e_score <= alpha:
                    return True, e_score, e_bm, alpha, beta
                beta = min(beta, e_score)

            if alpha >= beta:
                return True, e_score, e_bm, alpha, beta

        # No good cutoff but we can still return the best move for ordering efficiency
        return False, None, e_bm, alpha, beta

    def extract_pv(self, board: chess.Board, max_length: int = 10) -> list[str]:
        # Walk table to determine the principal variation line
        pv: list[str] = []
        seen: set = set()

        for _ in range(max_length):
            key = self._key(board)
            if key in seen:
                break
            seen.add(key)

            entry = self._table.get(key)
            if not entry:
                break

            _, _, _, best_move_uci = entry
            if not best_move_uci:
                break

            try:
                move = chess.Move.from_uci(best_move_uci)
                if move not in board.legal_moves:
                    break
                pv.append(best_move_uci)
                board.push(move)
            except Exception:
                break

        for _ in range(len(pv)):
            board.pop()

        return pv

    def __len__(self) -> int:
        return len(self._table)

    @staticmethod
    def _key(board: chess.Board):
        """Return the Zobrist transposition key for *board*."""
        if hasattr(board, "transposition_key"):
            return board.transposition_key()
        return board._transposition_key()

    @staticmethod
    def _entries_for_mb(size_mb: int) -> int:
        """Convert a megabyte budget into an entry count."""
        return max(50_000, size_mb * 25_000)
