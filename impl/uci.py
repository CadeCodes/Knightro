from __future__ import annotations

import sys
import logging
import os

import chess

from .evaluation import Evaluator
from .search import SearchEngine
from .transposition import TranspositionTable

class UCIHandler:
    # Supported UCI options with their defaults
    _DEFAULT_OPTIONS: dict[str, int | bool] = {
        "Move Overhead": 100,
        "Threads": 1,
        "Hash": 16,
        "UCI_ShowWDL": False,
    }

    def __init__(self) -> None:
        self.board = chess.Board()
        self.options: dict[str, int | bool] = dict(self._DEFAULT_OPTIONS)

        self._tt = TranspositionTable(size_mb=self.options["Hash"])
        self._evaluator = Evaluator()
        self._engine = SearchEngine(
            tt=self._tt,
            evaluator=self._evaluator,
            send=self._send,
        )

        self._logger = self._setup_logger()

    def run(self) -> None:
        # UCI Handshake
        for line in sys.stdin:
            line = line.strip()
            if line == "uci":
                self._handle_uci()
                break
            if line == "quit":
                return

        # UCI Command Loop
        for raw in sys.stdin:
            line = raw.strip()
            if not line:
                continue

            cmd, *args = line.split()

            match cmd:
                case "isready":
                    self._send("readyok")
                case "ucinewgame":
                    self._handle_new_game()
                case "setoption":
                    self._handle_setoption(args)
                case "position":
                    self._handle_position(args)
                case "go":
                    self._handle_go(args)
                case "stop":
                    pass  # search is synchronous — already finished
                case "quit":
                    break

    # UCI Handlers

    def _handle_uci(self) -> None:
        self._send(f"id name Knightro")
        self._send(f"id author CadeCodes")
        self._send("option name Move Overhead type spin default 100 min 0 max 5000")
        self._send("option name Threads type spin default 1 min 1 max 512")
        self._send("option name Hash type spin default 16 min 1 max 65536")
        self._send("option name UCI_ShowWDL type check default false")
        self._send("uciok")

    def _handle_new_game(self) -> None:
        self._tt.clear()
        self._engine.reset()

    def _handle_setoption(self, tokens: list[str]) -> None:
        raw = " ".join(tokens)
        if " value " in raw:
            name_part, val_part = raw.split(" value ", 1)
        else:
            name_part, val_part = raw, ""

        key = name_part.strip()
        val = val_part.strip()

        if key in ("Threads", "Hash", "Move Overhead"):
            try:
                self.options[key] = int(val)
            except ValueError:
                pass
            if key == "Hash":
                self._tt.resize(self.options["Hash"])
        elif key == "UCI_ShowWDL":
            self.options[key] = val.lower() in ("true", "1", "yes", "on")

    def _handle_position(self, args: list[str]) -> None:
        if not args:
            return

        kind, *rest = args

        if kind == "startpos":
            self.board = chess.Board()
            if rest and rest[0] == "moves":
                for m in rest[1:]:
                    self.board.push_uci(m)
        elif kind == "fen" and len(rest) >= 6:
            fen = " ".join(rest[:6])
            self.board = chess.Board(fen=fen)
            if len(rest) > 6 and rest[6] == "moves":
                for m in rest[7:]:
                    self.board.push_uci(m)

    def _handle_go(self, args: list[str]) -> None:
        my_time = 600_000  # Rapid 10m default
        increment = 0
        movetime: int | None = None

        for i, token in enumerate(args):
            if token == "wtime" and self.board.turn == chess.WHITE:
                my_time = int(args[i + 1])
            elif token == "btime" and self.board.turn == chess.BLACK:
                my_time = int(args[i + 1])
            elif token == "winc" and self.board.turn == chess.WHITE:
                increment = int(args[i + 1])
            elif token == "binc" and self.board.turn == chess.BLACK:
                increment = int(args[i + 1])
            elif token == "movetime":
                movetime = int(args[i + 1])

        # Manage time
        if movetime:
            time_limit = (movetime / 1000.0) - 0.05
        else:
            time_limit = (my_time / 1000.0 / 30.0) + (increment / 1000.0) - 0.05

        time_limit = max(time_limit, 0.05)

        # Trivial moves
        legal = list(self.board.legal_moves)
        if not legal:
            self._send("bestmove (none)")
            return
        if len(legal) == 1:
            self._send(f"bestmove {legal[0].uci()}")
            return

        # Run iterative-deepening search
        best_move, _score = self._engine.search(self.board, time_limit)
        self._send(f"bestmove {best_move.uci()}")

    @staticmethod
    def _send(msg: str) -> None:
        print(msg, flush=True)

    @staticmethod
    def _setup_logger() -> logging.Logger:
        log_path = os.path.join(os.path.dirname(__file__), "..", "knightro_errors.log")
        logger = logging.getLogger("knightro")
        logger.setLevel(logging.ERROR)
        if not logger.handlers:
            logger.addHandler(logging.FileHandler(log_path))
        return logger
