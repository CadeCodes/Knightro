from __future__ import annotations

import time
from typing import Callable

import chess

from .constants import INF, MATE, PIECE_VALUES, MAX_QS_DEPTH
from .evaluation import Evaluator
from .transposition import TranspositionTable, EXACT, LOWER, UPPER

# Find the best move in a position given a certain time budget
class SearchEngine:

    _MAX_KILLER_PLY: int = 100
    _SHUFFLE_DEMOTE: int = 500_000  # penalty for move reversal in root ordering

    def __init__(self, tt: TranspositionTable, evaluator: Evaluator, send: Callable[[str], None] | None = None) -> None:
        self.tt = tt
        self.evaluator = evaluator
        self._send = send or (lambda _msg: None)

        # Per-search counters
        self._nodes: int = 0
        self._start_time: float = 0.0
        self._time_limit: float = 0.0
        self._abort: bool = False

        # 2 slots per ply, cleared between games
        self._killers: list[list[chess.Move | None]] = [[None, None] for _ in range(self._MAX_KILLER_PLY)]

    def reset(self) -> None:
        # Only need to reset killer moves between games, TT is cleared separately by UCIHandlers
        for slot in self._killers:
            slot[0] = slot[1] = None

    def search(self, board: chess.Board, time_limit: float) -> tuple[chess.Move, int]:
        start_time = time.time()
        self._send(f"info string time limit {time_limit:.2f} seconds")

        legal = list(board.legal_moves)
        best_move = legal[0]
        best_score = 0

        for depth in range(1, 100):
            elapsed = time.time() - start_time

            # Soft limit, dont start a new iteration past 50% of time budget
            if depth > 1 and elapsed > time_limit * 0.5:
                break

            self.tt.evict_if_full()

            move, score = self._root_search(board, depth, start_time, time_limit)

            if move is not None:
                best_move = move
                best_score = score

                elapsed = time.time() - start_time
                nps = int(self._nodes / elapsed) if elapsed > 0 else 0
                pv = self.tt.extract_pv(board, max_length=15)
                pv_str = " ".join(pv) if pv else move.uci()
                uci_score = self._format_score(score)
                time_ms = int(elapsed * 1000)

                self._send(
                    f"info depth {depth} score {uci_score} "
                    f"nodes {self._nodes} nps {nps} time {time_ms} pv {pv_str}"
                )
            else:
                break  # hard time limit was hit, use previous iteration's result

        return best_move, best_score

    def _root_search(self, board: chess.Board, depth: int, start_time: float, time_limit: float) -> tuple[chess.Move | None, int]:
        self._start_time = start_time
        self._time_limit = time_limit
        self._nodes = 0
        self._abort = False

        best_score = -INF
        best_move: chess.Move | None = None
        alpha = -INF
        beta = INF

        last = board.move_stack[-1] if board.move_stack else None
        moves = list(board.legal_moves)

        # Consult TT for move ordering at root
        _, _, tt_bm_uci, _, _ = self.tt.probe(board, depth, alpha, beta)
        tt_move: chess.Move | None = None
        if tt_bm_uci:
            try:
                cand = chess.Move.from_uci(tt_bm_uci)
                if cand in moves:
                    tt_move = cand
            except Exception:
                pass

        def root_key(m: chess.Move) -> int:
            s = 0
            if tt_move and m == tt_move:
                s += 1_000_000
            if board.is_capture(m):
                s += self._mvv_lva(board, m)
            # Demote simple move reversal (prevent shuffling)
            if last and m.from_square == last.to_square and m.to_square == last.from_square:
                s -= self._SHUFFLE_DEMOTE
            return s

        moves.sort(key=root_key, reverse=True)

        for mv in moves:
            board.push(mv)
            score = -self._negamax(board, depth - 1, -beta, -alpha, 1)
            board.pop()

            if self._abort:
                return None, 0

            if score > best_score:
                best_score = score
                best_move = mv
            if score > alpha:
                alpha = score

        return best_move, best_score

    def _negamax(self, board: chess.Board, depth: int, alpha: int, beta: int, ply: int) -> int:

        # Time check
        self._nodes += 1
        if self._nodes % 1024 == 0:
            if time.time() - self._start_time >= self._time_limit:
                self._abort = True
        if self._abort:
            return alpha

        # Trivial cases
        if board.is_checkmate():
            return -(MATE - ply)
        if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
            return 0

        # Increase depth if in check (low cost, high value)
        in_check = board.is_check()
        if in_check and ply < 12:
            depth += 1

        # Leaf, move to quiescence search
        if depth <= 0:
            return self._quiescence(board, alpha, beta, 0)

        # Cheap cutoff for good captures before NMP
        orig_alpha = alpha
        hit, tt_score, tt_bm_uci, alpha, beta = self.tt.probe(board, depth, alpha, beta)
        if hit and tt_score is not None:
            return tt_score

        # Null move pruning
        has_majors = bool(board.occupied_co[board.turn] & ~board.pawns & ~board.kings)
        if depth >= 3 and not in_check and ply > 0 and has_majors:
            board.push(chess.Move.null())
            r = 2 if depth < 6 else 3
            score = -self._negamax(board, max(0, depth - r - 1), -beta, -beta + 1, ply + 1)
            board.pop()
            if score >= beta:
                return beta

        # TT -> captures -> (MVV-LVA) -> killers
        moves = list(board.legal_moves)

        def move_key(m: chess.Move) -> int:
            if tt_bm_uci and m.uci() == tt_bm_uci:
                return 1_000_000
            if board.is_capture(m):
                return self._mvv_lva(board, m)
            if m == self._killers[ply][0]:
                return 900_000
            if m == self._killers[ply][1]:
                return 800_000
            return 0

        moves.sort(key=move_key, reverse=True)

        best_score = -INF
        best_move: chess.Move | None = None

        for mv in moves:
            board.push(mv)
            score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1)
            board.pop()

            if score > best_score:
                best_score = score
                best_move = mv
            if score > alpha:
                alpha = score

            # Beta cutoff — store killer for quiet moves
            if score >= beta:
                if not board.is_capture(mv):
                    self._killers[ply][1] = self._killers[ply][0]
                    self._killers[ply][0] = mv
                break

        # Finally store result in TT
        flag = EXACT
        if best_score <= orig_alpha:
            flag = UPPER
        elif best_score >= beta:
            flag = LOWER

        self.tt.store(
            board, depth, best_score, flag,
            best_move.uci() if best_move else None,
        )
        return best_score

    # Search only tactical moves (captures, promotions, check evasions)
    def _quiescence(self, board: chess.Board, alpha: int, beta: int, qs_ply: int) -> int:
        in_check = board.is_check()

         # If not in check and the static eval already beats beta, we can assume no capture can make things worse for the opponent and cut off
        if not in_check:
            stand_pat = self.evaluator.evaluate_relative(board)
            if stand_pat >= beta:
                return beta
            if stand_pat > alpha:
                alpha = stand_pat

        if qs_ply >= MAX_QS_DEPTH:
            return self.evaluator.evaluate_relative(board)

        # Evasions when in check, otherwise only captures & promotions
        if in_check:
            moves = list(board.legal_moves)
        else:
            moves = [m for m in board.legal_moves if board.is_capture(m) or m.promotion is not None]

        moves.sort(key=lambda m: self._mvv_lva(board, m), reverse=True)

        for mv in moves:
            board.push(mv)
            score = -self._quiescence(board, -beta, -alpha, qs_ply + 1)
            board.pop()

            if score >= beta:
                return beta
            if score > alpha:
                alpha = score
                
        # Check + no way out = mate
        if in_check and alpha == -INF:
            return -MATE + qs_ply

        return alpha

    # Basic most valuable victim - least valuable attacker for ordering
    @staticmethod
    def _mvv_lva(board: chess.Board, move: chess.Move) -> int:
        if not board.is_capture(move):
            return -1
        victim = board.piece_at(move.to_square)
        attacker = board.piece_at(move.from_square)
        if not victim or not attacker:
            return -1
        return PIECE_VALUES[victim.piece_type] * 10 - PIECE_VALUES[attacker.piece_type]

    # Return a centipawn score for UCI, or mate if its close enough
    @staticmethod
    def _format_score(score: int) -> str:
        if abs(score) > 90_000:
            plies_to_mate = MATE - abs(score)
            moves_to_mate = (plies_to_mate + 1) // 2
            sign = 1 if score > 0 else -1
            return f"mate {sign * moves_to_mate}"
        return f"cp {score}"
