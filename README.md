<div align="center">

# Knightro

**A UCI chess engine written in Python**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](#requirements)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](#license)
[![UCI Protocol](https://img.shields.io/badge/protocol-UCI-orange)](#uci-options)

</div>

---

Knightro is a simplistic chess engine that communicates via the
[Universal Chess Interface](https://backscattering.de/chess/uci/) (UCI) protocol.
It pairs a classic alpha-beta search with custom heuristics and optimization techniques.
is compatible with any UCI GUI or [lichess-bot](https://github.com/lichess-bot-devs/lichess-bot).

## Features

### Search

| Technique | Details |
|---|---|
| **Alpha-beta negamax** | Fail-soft framework with PV tracking |
| **Iterative deepening** | Adjust depth on the fly to maximize search depth per movetime |
| **Transposition table** | Zobrist-keyed cache used for alpha-beta cutoff and move ordering |
| **Quiescence search** | Stand-pat pruning, promotion captures, and in-check evasions with mate detection |

### Evaluation Heuristics

All scores are in **centipawns** from White's perspective.

| Heuristic | Description |
|---|---|
| **Material** | Standard piece values |
| **Piece-square tables** | Per-square positional bonuses for every piece type |
| **Bishop pair** | +50 cp for holding both bishops |
| **Rook activity** | Bonus for rooks on open / semi-open files |
| **Passed pawns** | Exponential bonus for advanced passers |
| **King safety** | Pawn shield bonus on the back ranks |
| **King centrality** | King is rewarded for centering during endgame |
| **Tempo** | Standard small bonus for side to move |

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
Some GUIs will work with the python script directly, but some may require ```win_wrapper.bat``` to be used as the executable argument.

## UCI Options

| Option | Default | Range | Description |
|---|---|---|---|
| `Hash` | 16 | 1 – 65,536 | Transposition table size in MB |
| `Threads` | 1 | 1 – 512 | Not used currently |
| `Move Overhead` | 100 | 0 – 5 000 | Network/GUI latency buffer (ms) |

## Time Management

Knightro allocates **1 ⁄ 30** of remaining time plus increment per
move (if applicable), with a 50 ms safety margin.  When a `movetime` argument is passed via UCI, it is
used directly.  Iterative deepening stops early if 50 % of the budget is
already spent before the next iteration would begin.

## License

MIT © **CadeCodes**
