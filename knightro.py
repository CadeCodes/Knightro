import os
import logging

from impl.uci import UCIHandler

# Lightweight error logging as not all GUIs will capture stderr
_log_path = os.path.join(os.path.dirname(__file__), "knightro_errors.log")
_logger = logging.getLogger("knightro")
_logger.setLevel(logging.ERROR)
if not _logger.handlers:
    _logger.addHandler(logging.FileHandler(_log_path))


def main() -> None:
    UCIHandler().run()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        _logger.exception("Error during initialization")
        raise
