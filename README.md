# RRG-Lite

RRG-Lite is a Python CLI tool for displaying Relative Rotational graph (RRG) charts.

**Supports Python >= 3.8**

![RRG-Lite Charts](https://res.cloudinary.com/doyu4uovr/image/upload/s--fElRzmKh--/c_scale,f_auto,w_800/v1730368322/RRG-Lite/RRG-Lite-main_wrkwjk.png)

**Unlike traditional RRG charts,**

- Tickers are shown without tail lines or labels for a cleaner look. (See [Chart controls](#chart-controls))
- Mouse and keyboard controls enhance the user experience and aid in detailed analysis.

## Credits

This project was inspired and made possible due to the work of [An0n1mity/RRGPy](https://github.com/An0n1mity/RRGPy).

If you liked this project, please :star2: both our repos to encourage more inspirational works. :heart:

## Install

`git clone https://github.com/BennyThadikaran/RRG-Lite.git`

`pip install -r requirements.txt`

**v1.0.2 adds smooth curved tail lines.** This is an optional feature.

- Tail count must be above 4 else it defaults to straight lines.

To enable curved lines, install `scipy`.

`pip install scipy`

## Setup

See [Setting up configuration file](https://github.com/BennyThadikaran/RRG-Lite/wiki/Setup)

If you wish to use [EOD2](https://github.com/BennyThadikaran/eod2) as your data source, follow the [install instructions here](https://github.com/BennyThadikaran/eod2/wiki/Installation) to setup EOD2 and set `DATA_PATH` to `src/eod2_data/daily`

## Quick Usage

Make sure to setup your configuration file.

```bash
# assuming DATA_PATH, WATCHLIST_FILE and BENCHMARK has been setup
py init.py
```

**Pass a benchmark index using `-b` or `--benchmark` and a list of symbol names using `--sym`.**

`py init.py -b "nifty bank" --sym csbbank rblbank indianb ucobank`

**Pass a watchlist file using `-f` or `--file` option**

`py init.py -f nifty50.csv`

**To display help use `-h` option.**

`py init.py -h`

## Chart controls

**Left Mouse click on any point (marker)** to display/highlight the tail line and label.

Press **`delete`** to remove all highlighted lines.

Press **`h`** to toggle help text (Keybindings) in chart.

Press **`a`** to toggle displaying ticker labels (Annotations)

Press **`t`** to toggle tail lines for all tickers.

Press **`q`** to quit the chart.

Matplotlib provides useful window controls like zooming and panning. Read the links below on how to use the various tools.

To use zoom to rectangle tool - Press `o` (useful if plotting lots of symbols on chart.)

To reset the chart, press `r`

[Interactive navigation](https://matplotlib.org/stable/users/explain/figure/interactive.html#interactive-navigation)

[Navigation keyboard shortcuts](https://matplotlib.org/stable/users/explain/figure/interactive.html#navigation-keyboard-shortcuts)
