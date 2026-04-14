<div align="center">

# ♞ Knightro

**A UCI chess engine written in Python**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](#requirements)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](#license)
[![UCI Protocol](https://img.shields.io/badge/protocol-UCI-orange)](#uci-options)

</div>

---

Knightro is a from-scratch chess engine that communicates over the
[Universal Chess Interface](https://backscattering.de/chess/uci/) (UCI) protocol.
It pairs a classic alpha-beta search with hand-tuned evaluation heuristics and
is compatible with any UCI GUI or [lichess-bot](https://github.com/lichess-bot-devs/lichess-bot).

## Features

### Search

| Technique | Details |
|---|---|
| **Iterative deepening** | Soft limit (50 % of budget) prevents starting hopeless iterations |
| **Alpha-beta negamax** | Fail-soft framework with principal-variation tracking |
| **Transposition table** | Zobrist-keyed, depth-preferred replacement; used for move ordering and score cutoffs |
| **Null-move pruning** | Reduction R = 2 (depth < 6) or R = 3; skipped when in check or lacking major pieces |
| **Killer-move heuristic** | Two slots per ply for quiet-move ordering |
| **MVV-LVA ordering** | Most Valuable Victim – Least Valuable Attacker for capture sorting |
| **Check extensions** | Positions in check are searched one ply deeper |
| **Quiescence search** | Stand-pat pruning, promotion captures, and in-check evasions with mate detection |

### Evaluation

All scores are in **centipawns** from White's perspective; the side-to-move
wrapper flips the sign for a consistent negamax framework.

| Term | Description |
|---|---|
| **Material** | Standard piece values (P=100, N=320, B=330, R=500, Q=900) |
| **Piece-square tables** | Per-square positional bonuses for every piece type |
| **Bishop pair** | +50 cp for holding both bishops |
| **Rook activity** | Bonus for rooks on open / semi-open files |
| **Passed pawns** | Exponential bonus for advanced passers |
| **King safety** | Pawn-shield bonus on the back ranks |
| **King centralisation** | Endgame bonus (activates when ≤ 12 pieces remain) |
| **Tempo** | Small bonus (+10 cp) for the side to move |

## Project Structure

```
knightro.py              # UCI entry point
impl/
├── __init__.py          # Package metadata
├── constants.py         # Piece values, piece-square tables, search params
├── evaluation.py        # Static board evaluation
├── transposition.py     # Zobrist-keyed transposition table
├── search.py            # Alpha-beta negamax with iterative deepening
└── uci.py               # UCI protocol handler
```

## Requirements

- **Python 3.10+**
- [`python-chess`](https://python-chess.readthedocs.io/)

```bash
pip install chess
```

## Usage

```bash
python knightro.py
```

Knightro reads UCI commands from `stdin` and writes responses to `stdout`.
Point any UCI-compatible GUI (Arena, CuteChess, etc.) or lichess-bot at the
script and it will handle the rest.

## UCI Options

| Option | Type | Default | Range | Description |
|---|---|---|---|---|
| `Hash` | spin | 16 | 1 – 65 536 | Transposition table size in MB |
| `Threads` | spin | 1 | 1 – 512 | *(reserved for future use)* |
| `Move Overhead` | spin | 100 | 0 – 5 000 | Network/GUI latency buffer (ms) |
| `UCI_ShowWDL` | check | false | — | Show win/draw/loss statistics |

## Time Management

Knightro allocates **1 ⁄ 30** of remaining time plus the full increment per
move, with a 50 ms safety margin.  When a `movetime` value is provided it is
used directly.  Iterative deepening stops early if 50 % of the budget is
already spent before the next iteration would begin.

## License

MIT © **CadeCodes**
