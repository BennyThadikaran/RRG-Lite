# RRG-Lite

RRG-Lite is a Python CLI tool for displaying Relative Rotation graph (RRG) charts.

**Supports Python >= 3.8**

![RRG-Lite Charts](https://res.cloudinary.com/doyu4uovr/image/upload/s--iD51VT-2--/f_auto/v1731069111/RRG-Lite/rrg-lite-main_ggsdbr.png)

An RRG (Relative Rotation Graph) chart is used to analyze the relative strength and momentum of multiple stocks or sectors compared to a benchmark (usually a market index like the S&P 500 or Nifty 50).

It provides a bird's-eye view of how various stocks or sectors are performing relative to the benchmark over time.

RRG charts can help identify which stocks or sectors are outperforming or underperforming the index.

They are useful for asset allocation decisions and for identifying both momentum stocks and potential bottom-fishing opportunities.

Read more about [RRG - Investopedia.com](https://www.investopedia.com/relative-rotation-graph-8418457)

**Unlike traditional RRG charts,**

- Tickers are shown without tail lines or labels for a cleaner look. (See [Chart controls](#chart-controls))
- Mouse and keyboard controls enhance the user experience and aid in detailed analysis.

**By default,**

- The timeframe is weekly and 14 week average is used for calculations.
- The RS momentum is calculated by comparing the current value to its value from 52 weeks ago.
- See wiki for explanation of [RS ratio and Momentum calculations](https://github.com/BennyThadikaran/RRG-Lite/wiki/RS-ratio-and-Momentum-calculations)

## Credits

This project was inspired and made possible due to the work of [An0n1mity/RRGPy](https://github.com/An0n1mity/RRGPy).

If you liked this project, please :star2: the repos to encourage more inspirational works. :heart:

## Install

`git clone https://github.com/BennyThadikaran/RRG-Lite.git`

`pip install -r requirements.txt`

**Optional:** To enable curved tail lines, install `scipy`.

`pip install scipy`

- If tail count is less than 3, it defaults to straight lines.

![Curved tail lines](https://res.cloudinary.com/doyu4uovr/image/upload/s--x4RTqGdv--/f_auto/v1731069415/RRG-Lite/rrg-lite-curved-line_pd5int.png)

## Setup

To get started, you need a folder containing OHLC data (Daily timeframe or higher) in CSV format.

**Folder must contain:** 

1. Atleast one Benchmark index file.
2. One or more stock / etf / sector files.

Create a `user.json` file in `src/` as below

```json
{
  "DATA_PATH": "full/path/to/data/folder/"
}
```

`DATA_PATH` must be a folder path, where OHLC data is stored. Above is the minumum configuration required to get started.

See [additional configuration options](https://github.com/BennyThadikaran/RRG-Lite/wiki/Setup)

#### Use EOD2 as data source

If you need data on Indian Stocks (NSE), you can try [EOD2](https://github.com/BennyThadikaran/eod2) and [follow install instructions here](https://github.com/BennyThadikaran/eod2/wiki/Installation) to setup EOD2.

Once EOD2 is setup, follow the [setup instructions](#setup), and set `DATA_PATH` to the full path to EOD2 daily folder located in `src/eod2_data/daily/`.

You can download my sectors watchlist file that works with EOD2 - [sectors.csv](https://res.cloudinary.com/doyu4uovr/raw/upload/v1730526283/RRG-Lite/sectors_vwqau3.csv)

## Quick Usage

**Pass a benchmark index using `-b` and a list of symbol names using `--sym`.**

`py init.py -b "nifty bank" --sym csbbank rblbank`

**Note:** In the above example, it will look for files named `nifty bank.csv`, `csbbank.csv`, and `rblbank.csv` in the `DATA_PATH` folder

**Pass a watchlist file using `-f` option**

`py init.py -b 'nifty 50' -f sectors.csv`

**Note:** See details on [setting up a watchlist](https://github.com/BennyThadikaran/RRG-Lite/wiki/Setup#watchlist-file-format)

**To display help, use the `-h` option.**

`py init.py -h`

## Chart controls

**Left Mouse click on any point (marker)** to display/highlight the tail line and label.

**When a line is highlighted:**

- Press `Left arrow` or `Right arrow` keys to cycle through each marker on the line, diplaying a date label. (see image below)
- Press **`delete`** to remove all highlighted lines.

![date labels in rrg chart](https://res.cloudinary.com/doyu4uovr/image/upload/s--YQhUxYZK--/f_auto/v1731069111/RRG-Lite/rrg-lite-date-labels_y5ba0o.png)

Press **`h`** to toggle help text (Keybindings) in the chart.

Press **`a`** to toggle displaying ticker labels (Annotations)

Press **`t`** to toggle tail lines for all tickers.

Press **`q`** to quit the chart.

To reset the chart, press **`r`**

To use the `zoom to rectangle` tool - Press **`o`** (useful when lots of symbols on the chart.)

Matplotlib provides useful window controls like zooming and panning. Read the links below on how to use the various tools.

[Interactive navigation](https://matplotlib.org/stable/users/explain/figure/interactive.html#interactive-navigation)

[Navigation keyboard shortcuts](https://matplotlib.org/stable/users/explain/figure/interactive.html#navigation-keyboard-shortcuts)

## Streamlit Dashboard

This project now includes an interactive web-based dashboard built with Streamlit, allowing for a more user-friendly way to generate and visualize RRG charts.

**Features:**

*   Interactive UI to select benchmark, symbols (via text input or file upload), and RRG parameters (tail length, timeframe, RS-Ratio window, RS-Momentum period, end date).
*   Real-time chart generation based on your inputs.
*   Displays warnings for data loading issues without halting the entire process if some symbols are valid.
*   Uses the same `src/user.json` for initial configuration (like `DATA_PATH`).

**Running the Dashboard:**

1.  **Ensure Streamlit is installed:**
    If you haven't already, install Streamlit. It's included in `requirements.txt`.
    ```bash
    pip install streamlit
    ```
    Or, if you've cloned the project and want to install all dependencies:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Navigate to the project root directory** in your terminal.

3.  **Run the Streamlit app:**
    ```bash
    streamlit run dashboard.py
    ```
    This will typically open the dashboard in your default web browser.

**Configuration:**

The dashboard uses the `src/user.json` file for its initial setup, particularly for the `DATA_PATH` where your CSV data files are stored. Ensure this file is correctly configured as described in the [Setup](#setup) section. The dashboard also allows overriding many parameters through its UI.
