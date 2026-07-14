import sys
from pathlib import Path

import utils
from RRG import RRG, version

if "-v" in sys.argv or "--version" in sys.argv:
    exit(
        f"""
        RRG-Lite | Version {version}
        Copyright (C) 2024 Benny Thadikaran 

        Github: https://github.com/BennyThadikaran/RRG-Lite

        This program comes with ABSOLUTELY NO WARRANTY.
        This is free software, and you are welcome to redistribute it
        under certain conditions.
        See license: https://www.gnu.org/licenses/gpl-3.0.en.html#license-text
        """
    )

if "-h" in sys.argv or "--help" in sys.argv:
    utils.parse_cli_options()
    exit(0)

config = utils.load_config()

if not config:
    exit("Configuration file is missing.")

data_path_string = config.get("DATA_PATH", "")

data_path = Path(data_path_string).expanduser()

if data_path_string == "" or not data_path.exists():
    exit("`DATA_PATH` not found or not provided. Edit user.json.")

watchlist_file = config.get("WATCHLIST_FILE", None)

if watchlist_file and not (
    "-f" in sys.argv or "--file" in sys.argv or "--sym" in sys.argv
):
    sys.argv.extend(("-f", watchlist_file))

args = utils.parse_cli_options()

loader_class = utils.get_loader_class(config)

watchlist = args.file.read_text().strip().split("\n") if args.file else args.sym

rrg = RRG(
    config,
    watchlist=watchlist,
    tail_count=args.tail,
    benchmark=args.benchmark,
    tf=args.tf,
    end_date=args.date,
)

rrg.plot()
