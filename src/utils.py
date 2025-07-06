import importlib
import json
import sys
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path


def load_config(config_file_path: Optional[str] = None):
    """Loads the configuration file.
    If config_file_path is provided, it's used.
    Otherwise, it checks CLI arguments for a config path.
    Finally, it defaults to 'user.json' in the 'src' directory.
    """
    if config_file_path:
        config_path = Path(config_file_path).expanduser().resolve()
    elif "-c" in sys.argv or "--config" in sys.argv:
        idx = sys.argv.index("-c" if "-c" in sys.argv else "--config") + 1
        config_path = Path(sys.argv[idx]).expanduser().resolve()
    else:
        # Default path relative to this file's parent directory (src)
        config_path = Path(__file__).parent / "user.json"

    if config_path.exists():
        try:
            return json.loads(config_path.read_bytes())
        except Exception as e:
            print(f"Error loading config file {config_path}: {e}")
            return None
    else:
        print(f"Config file not found at {config_path}")
        return None


def get_loader_class(config):
    # Load data loader from config. Default loader is EODFileLoader
    loader_name = config.get("LOADER", "EODFileLoader")

    loader_module = importlib.import_module(f"loaders.{loader_name}")

    return getattr(loader_module, loader_name)


def parse_cli_options():
    # Add CLI options
    parser = ArgumentParser(
        description="Python CLI tool to plot RRG charts",
        epilog="https://github.com/BennyThadikaran/RRG-Lite",
    )

    parser.add_argument(
        "-c",
        "--config",
        type=lambda x: Path(x).expanduser().resolve(),
        metavar="filepath",
        help="Custom config file",
    )

    parser.add_argument(
        "-d",
        "--date",
        type=datetime.fromisoformat,
        metavar="str",
        help="ISO format date YYYY-MM-DD.",
    )

    parser.add_argument(
        "--tf",
        action="store",
        default="weekly",
        help="Timeframe string.",
    )

    parser.add_argument(
        "-t",
        "--tail",
        type=int,
        default=4,
        metavar="int",
        help="Length of tail. Default 3",
    )

    parser.add_argument(
        "-b",
        "--benchmark",
        default=None,
        metavar="str",
        help="Benchmark index name",
    )

    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument(
        "-f",
        "--file",
        type=lambda x: Path(x).expanduser().resolve(),
        default=None,
        metavar="filepath",
        help="File containing list of stocks. One on each line",
    )

    group.add_argument(
        "--sym",
        nargs="+",
        metavar="SYM",
        help="Space separated list of stock symbols.",
    )

    group.add_argument(
        "-v",
        "--version",
        action="store_true",
        help="Print the current version.",
    )

    return parser.parse_args()
