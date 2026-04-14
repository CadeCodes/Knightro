from __future__ import annotations

import chess

from .constants import PIECE_VALUES, PIECE_SQUARE_TABLES

# Stateless board evaluator class, all public methods are pure functions of the board with no internal state, so a single instance can be shared freely.
class Evaluator:
    # Return a eval score from whites perspective
    def evaluate(self, board: chess.Board) -> int:
        # Retrieve piece bitboards for both sides
        wp = board.pieces(chess.PAWN, chess.WHITE)
        bp = board.pieces(chess.PAWN, chess.BLACK)
        wn = board.pieces(chess.KNIGHT, chess.WHITE)
        bn = board.pieces(chess.KNIGHT, chess.BLACK)
        wb = board.pieces(chess.BISHOP, chess.WHITE)
        bb = board.pieces(chess.BISHOP, chess.BLACK)
        wr = board.pieces(chess.ROOK, chess.WHITE)
        br = board.pieces(chess.ROOK, chess.BLACK)
        wq = board.pieces(chess.QUEEN, chess.WHITE)
        bq = board.pieces(chess.QUEEN, chess.BLACK)

        wk_sq = board.king(chess.WHITE)
        bk_sq = board.king(chess.BLACK)

        # Material Sum
        material = (
            (len(wp) - len(bp)) * 100
            + (len(wn) - len(bn)) * 320
            + (len(wb) - len(bb)) * 330
            + (len(wr) - len(br)) * 500
            + (len(wq) - len(bq)) * 900
        )

        # PSTs (note ^ 56 to mirror for Black)
        pst_score = 0
        piece_sets = {
            chess.PAWN: (wp, bp),
            chess.KNIGHT: (wn, bn),
            chess.BISHOP: (wb, bb),
            chess.ROOK: (wr, br),
            chess.QUEEN: (wq, bq),
        }

        for piece_type, table in PIECE_SQUARE_TABLES.items():
            if piece_type == chess.KING:
                if wk_sq is not None:
                    pst_score += table[wk_sq ^ 56]
                if bk_sq is not None:
                    pst_score -= table[bk_sq]
            else:
                w_set, b_set = piece_sets[piece_type]
                for sq in w_set:
                    pst_score += table[sq ^ 56]
                for sq in b_set:
                    pst_score -= table[sq]

        # Reward pair of bishops
        bishop_pair = 0
        if len(wb) >= 2:
            bishop_pair += 50
        if len(bb) >= 2:
            bishop_pair -= 50

        # Reward rooks on open or "semi-open" files
        rook_bonus = self._rook_file_bonus(wr, wp, bp) - self._rook_file_bonus(br, bp, wp)

        # Reward passed pawns 
        passed_pawn_bonus = (
            self._passed_pawn_score_white(wp, bp)
            - self._passed_pawn_score_black(bp, wp)
        )

        # Reward king safety
        king_safety = (
            self._king_shield_white(wk_sq, wp, wq, wr)
            - self._king_shield_black(bk_sq, bp, bq, br)
        )

        # Reward king centrality in endgames (total pieces <= 12)
        total_pieces = (
            len(wp) + len(bp) + len(wn) + len(bn)
            + len(wb) + len(bb) + len(wr) + len(br)
            + len(wq) + len(bq)
        )
        king_activity = 0
        if total_pieces <= 12:
            king_activity = (
                self._king_centrality(wk_sq)
                - self._king_centrality(bk_sq)
            )

        # Reward tempo, always +10 since perspective from white
        tempo = 10

        return (
            material + pst_score + bishop_pair + rook_bonus
            + passed_pawn_bonus + king_safety + king_activity + tempo
        )
    
    # Flip white perspective eval for black to maintain negamax consistency
    def evaluate_relative(self, board: chess.Board) -> int:
        score = self.evaluate(board)
        return score if board.turn == chess.WHITE else -score

    @staticmethod
    def _rook_file_bonus(rooks: chess.SquareSet, friendly_pawns: chess.SquareSet, enemy_pawns: chess.SquareSet) -> int:
        bonus = 0
        for sq in rooks:
            file_bb = chess.BB_FILES[chess.square_file(sq)]
            if not (friendly_pawns & file_bb):
                bonus += 20 if not (enemy_pawns & file_bb) else 10
        return bonus

    @staticmethod
    def _passed_pawn_score_white(white_pawns: chess.SquareSet, black_pawns: chess.SquareSet) -> int:
        bonus = 0
        for sq in white_pawns:
            rank = chess.square_rank(sq)
            if rank >= 4:
                file = chess.square_file(sq)
                ahead_mask = 0
                for r in range(rank + 1, 8):
                    ahead_mask |= chess.BB_FILES[file] & chess.BB_RANK_MASKS[r]
                if not (black_pawns & ahead_mask):
                    bonus += 20 * (2 ** (rank - 4))
        return bonus

    @staticmethod
    def _passed_pawn_score_black(black_pawns: chess.SquareSet, white_pawns: chess.SquareSet) -> int:
        bonus = 0
        for sq in black_pawns:
            rank = chess.square_rank(sq)
            if rank <= 3:
                file = chess.square_file(sq)
                ahead_mask = 0
                for r in range(0, rank):
                    ahead_mask |= chess.BB_FILES[file] & chess.BB_RANK_MASKS[r]
                if not (white_pawns & ahead_mask):
                    bonus += 20 * (2 ** (3 - rank))
        return bonus

    @staticmethod
    def _king_shield_white(king_sq: int | None, pawns: chess.SquareSet, queens: chess.SquareSet, rooks: chess.SquareSet) -> int:
        if king_sq is None or not (queens or rooks):
            return 0
        kf = chess.square_file(king_sq)
        kr = chess.square_rank(king_sq)
        bonus = 0
        if kr < 2:
            for offset in (-1, 0, 1):
                f = kf + offset
                if 0 <= f < 8:
                    if pawns & chess.BB_SQUARES[chess.square(f, 1)]:
                        bonus += 10
                    elif kr == 0 and (pawns & chess.BB_SQUARES[chess.square(f, 0)]):
                        bonus -= 15
        return bonus

    @staticmethod
    def _king_shield_black(king_sq: int | None, pawns: chess.SquareSet, queens: chess.SquareSet, rooks: chess.SquareSet) -> int:
        if king_sq is None or not (queens or rooks):
            return 0
        kf = chess.square_file(king_sq)
        kr = chess.square_rank(king_sq)
        bonus = 0
        if kr > 5:
            for offset in (-1, 0, 1):
                f = kf + offset
                if 0 <= f < 8:
                    if pawns & chess.BB_SQUARES[chess.square(f, 6)]:
                        bonus += 10
                    elif kr == 7 and (pawns & chess.BB_SQUARES[chess.square(f, 7)]):
                        bonus -= 15
        return bonus

    @staticmethod
    def _king_centrality(king_sq: int | None) -> int:
        if king_sq is None:
            return 0
        kf = chess.square_file(king_sq)
        kr = chess.square_rank(king_sq)
        return int((3 - abs(kf - 3.5)) * 3 + (3 - abs(kr - 3.5)) * 3)
