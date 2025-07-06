import sys
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import utils

try:
    from scipy import interpolate

    scipy_installed = True
except ModuleNotFoundError:
    scipy_installed = False

version = "1.0.9"


class RRG:
    def __init__(
        self,
        config: dict,
        watchlist: list,
        tail_count=4,
        benchmark=None,
        **kwargs,
    ):
        self.watchlist = watchlist

        benchmark_config = config.get("BENCHMARK", None)

        if benchmark:
            self.benchmark = benchmark
        elif benchmark_config:
            self.benchmark = benchmark_config
        else:
            raise ValueError(
                "No benchmark index set. Use `-b` or specify `BENCHMARK` in config."
            )

        # Tail count set to minimum 2
        self.tail_count = max(2, tail_count)

        # self.window = config.get("WINDOW", 14) # Overridden by kwargs if present
        # self.period = config.get("PERIOD", 52) # Overridden by kwargs if present
        self.config = config

        # Allow overriding window and period from kwargs (e.g., Streamlit UI)
        self.window = kwargs.get("window", config.get("WINDOW", 14))
        self.period = kwargs.get("period", config.get("PERIOD", 52))


        # Keep track of data points, lines and text annotations
        self.state = {}

        # Keep track of the alpha state of lines and text
        self.text_alpha_state = 0
        self.line_alpha_state = 0

        # Default alpha values for lines and text
        self.text_alpha = 0.6
        self.line_alpha = 0.5

        self.minimum_data_length = max(
            self.window * 2 + self.tail_count,
            self.window + self.period + self.tail_count,
        )

        loader_class = utils.get_loader_class(config)

        self.loader = loader_class(
            config, period=self.minimum_data_length, **kwargs
        )

        self.help_plt = None

        self.help_str = """
        Keyboard Shortcuts

        delete - Remove all lines and annotations
        a         - Toggle text annotations
        t          - Toggle tail lines
        h         - Print this help text

        Mouse interaction

        Left click on Marker to toggle visibility of 
        tail, markers and labels
        """

        # Map keyboard shortcuts to their relevant handlers
        self.key_handler = dict(
            delete=self._clear_all,
            a=self._toggle_text,
            t=self._toggle_lines,
            h=self._toggle_help,
            left=self._cycle_dates,
            right=self._cycle_dates,
        )

        # properties to help track date labels when cycling through them.
        # Activated when a tail line is highlighted
        self.tabbable = False
        self.tabindex = 0
        self.highlighted_count = 0
        self.active_date_labels = []

    def plot(self):
        txt_alpha = 0.4

        # colors = np.random.rand(len(self.watchlist), 3) * 0.6

        bm = self.loader.get(self.benchmark)

        if bm is None or bm.empty:
            raise ValueError(
                f"Unable to load benchmark data for {self.benchmark}"
            )

        if len(bm) < self.minimum_data_length:
            raise ValueError("Benchmark data is insufficient to plot chart.")

        bm_closes = self._process_ser(bm.loc[:, "Close"])

        # Setup the chart
        self.fig, axs = plt.subplots()
        axs.format_coord = self._format_coords

        plt.tight_layout()

        axs.set_title(
            f"RRG - {self.benchmark.upper()} - {bm.index[-1]:%d %b %Y}"
        )
        axs.set_xlabel("RS Ratio")
        axs.set_ylabel("RS Momentum")

        # Center line that divided the quadrant
        axs.axhline(y=100, color="black", linestyle="--", linewidth=0.3)
        axs.axvline(x=100, color="black", linestyle="--", linewidth=0.3)

        # Background colors for each quadrant
        axs.fill_between([93.5, 100], 100, 106.5, color="#b1ebff")
        axs.fill_between([100, 106.5], 100, 106.5, color="#bdffc9")
        axs.fill_between([100, 106.5], 93.5, 100, color="#fff7b8")
        axs.fill_between([93.5, 100], 93.5, 100, color="#ffb9c6")

        x_max = y_max = 0
        x_min = y_min = 200

        # Start calculation of RS and RS Momentum
        for i, ticker in enumerate(self.watchlist):
            short_name = None

            if "," in ticker:
                ticker, short_name = ticker.split(",")

            if short_name is None:
                short_name = ticker

            df = self.loader.get(ticker)

            if df is None or df.empty:
                continue

            ser_closes = self._process_ser(df.loc[:, "Close"])

            rsr = self._calculate_rs(ser_closes, bm_closes)

            rsm = self._calculate_momentum(rsr)

            if min(len(rsm), len(rsr)) < self.tail_count:
                print(f"Unable to load `{ticker.upper()}`: Insufficient data")
                continue

            rsr_line = rsr.iloc[-self.tail_count :]
            rsm_line = rsm.iloc[-self.tail_count :]

            color = self._get_color(rsr.iloc[-1], rsm.iloc[-1])

            if rsr_line.max() > x_max:
                x_max = rsr_line.max()

            if rsr_line.min() < x_min:
                x_min = rsr_line.min()

            if rsm_line.max() > y_max:
                y_max = rsm_line.max()

            if rsm_line.min() < y_min:
                y_min = rsm_line.min()

            annotation = axs.annotate(
                short_name.upper(),
                xy=(rsr.iloc[-1], rsm.iloc[-1]),
                xytext=(5, -3),
                textcoords="offset points",
                horizontalalignment="left",
                alpha=0,
            )

            # Plot the head marker (latest data point - Visible)
            marker = axs.scatter(
                x=rsr.iloc[-1],
                y=rsm.iloc[-1],
                s=40,
                color=color,
                marker="o",
                picker=True,
            )

            url = f"s{i}"
            marker.set_url(url)

            # Plot the tail markers (Not visible by default)
            markers = axs.scatter(
                x=rsr.iloc[-self.tail_count : -1],
                y=rsm.iloc[-self.tail_count : -1],
                c=color,
                s=20,
                marker="o",
                alpha=0,
            )

            if scipy_installed and self.tail_count > 2:
                x, y = self._get_smooth_curve(
                    rsr.iloc[-self.tail_count :], rsm.iloc[-self.tail_count :]
                )
            else:
                x = rsr.iloc[-self.tail_count :]
                y = rsm.iloc[-self.tail_count :]

            line = axs.plot(
                x,
                y,
                linestyle="-",
                color=color,
                linewidth=1.2,
                alpha=0,
            )[0]

            # apply date annotations to the tail markers
            # Head marker date text is set to bold
            date_annotations = tuple(
                axs.annotate(
                    idx.strftime("%d %b %Y"),
                    xy=(rsr.loc[idx], rsm.loc[idx]),
                    xytext=(-5, -3),
                    textcoords="offset points",
                    horizontalalignment="right",
                    alpha=0,
                    zorder=100,
                    fontweight=("bold" if idx == rsr.index[-1] else "normal"),
                )
                for idx in rsr.index[-self.tail_count :]
            )

            self.state[url] = dict(
                line=line,
                markers=markers,
                annotation=annotation,
                dates=date_annotations,
            )

        axs.set_xlim(x_min - 0.3, x_max + 0.3)
        axs.set_ylim(y_min - 0.3, y_max + 0.3)

        # Labels for each quadrant
        if x_min < 100 and y_max > 100:
            axs.text(
                x_min - 0.2,
                y_max,
                "Improving",
                fontweight="bold",
                alpha=txt_alpha,
            )

        if x_max > 100 and y_max > 100:
            axs.text(
                x_max - 0.1,
                y_max,
                "Leading",
                fontweight="bold",
                alpha=txt_alpha,
            )

        if x_max > 100 and y_min < 100:
            axs.text(
                x_max - 0.2,
                y_min,
                "Weakening",
                fontweight="bold",
                alpha=txt_alpha,
            )

        if x_min < 100 and y_min < 100:
            axs.text(
                x_min - 0.2,
                y_min,
                "Lagging",
                fontweight="bold",
                alpha=txt_alpha,
            )

        self.fig.canvas.mpl_connect("pick_event", self._on_pick)
        self.fig.canvas.mpl_connect("key_press_event", self._on_key_press)

        # Display the chart window in full screen
        window_manager = plt.get_current_fig_manager()

        if window_manager:
            if "win" in sys.platform:
                try:
                    # Only works with tkAgg backend
                    window_manager.window.state("zoomed")
                except AttributeError:
                    window_manager.full_screen_toggle()
            else:
                window_manager.full_screen_toggle()

        self.axs = axs
        # plt.show() # Removed for Streamlit compatibility
        return self.fig

    def prepare_rrg_data(self):
        """
        Loads data, calculates RS Ratio and RS Momentum, and prepares
        all necessary data for plotting the RRG chart.
        Returns a dictionary containing plot data.
        """
        bm = self.loader.get(self.benchmark)

        if bm is None or bm.empty:
            raise ValueError(
                f"Unable to load benchmark data for {self.benchmark}"
            )

        if len(bm) < self.minimum_data_length:
            raise ValueError("Benchmark data is insufficient to plot chart.")

        bm_closes = self._process_ser(bm.loc[:, "Close"])

        warnings = []
        plot_data = {
            "benchmark_name": self.benchmark.upper(),
            "benchmark_date": bm.index[-1],
            "tickers_data": [],
            "x_min": 200, "x_max": 0, "y_min": 200, "y_max": 0,
            "warnings": warnings,
        }

        for i, ticker_entry in enumerate(self.watchlist):
            ticker, short_name = ticker_entry, ticker_entry
            if "," in ticker_entry:
                ticker, short_name = ticker_entry.split(",", 1)

            # The loader itself might produce warnings (e.g. file not found if we adapt it)
            # For now, loader.get() returns None or empty df on failure.
            df_load_result = self.loader.get(ticker)

            df = None
            if isinstance(df_load_result, tuple): # Assuming loader might return (df, loader_warnings)
                df, loader_warnings = df_load_result
                warnings.extend(loader_warnings)
            else: # Current loader returns df or None
                df = df_load_result

            if df is None or df.empty:
                warnings.append(f"Warning: Unable to load data for `{ticker.upper()}`. It will be skipped.")
                continue

            ser_closes = self._process_ser(df.loc[:, "Close"])
            rsr = self._calculate_rs(ser_closes, bm_closes)
            rsm = self._calculate_momentum(rsr)

            if min(len(rsm), len(rsr)) < self.tail_count:
                warnings.append(f"Warning: Insufficient data for `{ticker.upper()}` to meet tail count ({self.tail_count}). It will be skipped.")
                continue

            rsr_line = rsr.iloc[-self.tail_count :]
            rsm_line = rsm.iloc[-self.tail_count :]

            current_rsr = rsr.iloc[-1]
            current_rsm = rsm.iloc[-1]

            color = self._get_color(current_rsr, current_rsm)

            plot_data["x_max"] = max(plot_data["x_max"], rsr_line.max())
            plot_data["x_min"] = min(plot_data["x_min"], rsr_line.min())
            plot_data["y_max"] = max(plot_data["y_max"], rsm_line.max())
            plot_data["y_min"] = min(plot_data["y_min"], rsm_line.min())

            ticker_data = {
                "id": f"s{i}",
                "short_name": short_name.upper(),
                "rsr_latest": current_rsr,
                "rsm_latest": current_rsm,
                "rsr_tail": rsr_line,
                "rsm_tail": rsm_line,
                "color": color,
                "raw_rsr": rsr, # For date annotations
                "raw_rsm": rsm, # For date annotations
            }
            plot_data["tickers_data"].append(ticker_data)

        if not plot_data["tickers_data"]:
             raise ValueError("No ticker data could be processed for the RRG chart.")

        return plot_data

    def generate_rrg_figure(self, plot_data: dict):
        """
        Generates the Matplotlib figure for the RRG chart using pre-calculated data.
        """
        txt_alpha = 0.4
        self.fig, axs = plt.subplots()
        axs.format_coord = self._format_coords
        plt.tight_layout()

        axs.set_title(
            f"RRG - {plot_data['benchmark_name']} - {plot_data['benchmark_date']:%d %b %Y}"
        )
        axs.set_xlabel("RS Ratio")
        axs.set_ylabel("RS Momentum")

        axs.axhline(y=100, color="black", linestyle="--", linewidth=0.3)
        axs.axvline(x=100, color="black", linestyle="--", linewidth=0.3)

        axs.fill_between([93.5, 100], 100, 106.5, color="#b1ebff") # Improving
        axs.fill_between([100, 106.5], 100, 106.5, color="#bdffc9") # Leading
        axs.fill_between([100, 106.5], 93.5, 100, color="#fff7b8") # Weakening
        axs.fill_between([93.5, 100], 93.5, 100, color="#ffb9c6") # Lagging

        # Reset state for new plot
        self.state = {}

        for ticker_data in plot_data["tickers_data"]:
            annotation = axs.annotate(
                ticker_data["short_name"],
                xy=(ticker_data["rsr_latest"], ticker_data["rsm_latest"]),
                xytext=(5, -3),
                textcoords="offset points",
                horizontalalignment="left",
                alpha=0, # Initially hidden, controlled by _toggle_text or pick event
            )

            marker = axs.scatter(
                x=ticker_data["rsr_latest"],
                y=ticker_data["rsm_latest"],
                s=40,
                color=ticker_data["color"],
                marker="o",
                picker=True, # Allows interaction if event handlers are connected
            )
            marker.set_url(ticker_data["id"])

            markers_tail = axs.scatter(
                x=ticker_data["rsr_tail"][:-1],
                y=ticker_data["rsm_tail"][:-1],
                c=ticker_data["color"],
                s=20,
                marker="o",
                alpha=0, # Initially hidden
            )

            if scipy_installed and self.tail_count > 2:
                x_smooth, y_smooth = self._get_smooth_curve(
                    ticker_data["rsr_tail"], ticker_data["rsm_tail"]
                )
            else:
                x_smooth = ticker_data["rsr_tail"]
                y_smooth = ticker_data["rsm_tail"]

            line = axs.plot(
                x_smooth,
                y_smooth,
                linestyle="-",
                color=ticker_data["color"],
                linewidth=1.2,
                alpha=0, # Initially hidden
            )[0]

            # Date annotations (initially hidden)
            # Need raw rsr and rsm for correct date indexing
            raw_rsr_for_dates = ticker_data["raw_rsr"].iloc[-self.tail_count:]
            raw_rsm_for_dates = ticker_data["raw_rsm"].iloc[-self.tail_count:]

            date_annotations = tuple(
                axs.annotate(
                    idx.strftime("%d %b %Y"),
                    xy=(raw_rsr_for_dates.loc[idx], raw_rsm_for_dates.loc[idx]),
                    xytext=(-5, -3),
                    textcoords="offset points",
                    horizontalalignment="right",
                    alpha=0,
                    zorder=100,
                    fontweight=("bold" if idx == raw_rsr_for_dates.index[-1] else "normal"),
                )
                for idx in raw_rsr_for_dates.index
            )

            self.state[ticker_data["id"]] = dict(
                line=line,
                markers=markers_tail,
                annotation=annotation,
                dates=date_annotations,
            )

        axs.set_xlim(plot_data["x_min"] - 0.3, plot_data["x_max"] + 0.3)
        axs.set_ylim(plot_data["y_min"] - 0.3, plot_data["y_max"] + 0.3)

        # Quadrant Labels
        if plot_data["x_min"] < 100 and plot_data["y_max"] > 100:
            axs.text(plot_data["x_min"] - 0.2, plot_data["y_max"], "Improving", fontweight="bold", alpha=txt_alpha)
        if plot_data["x_max"] > 100 and plot_data["y_max"] > 100:
            axs.text(plot_data["x_max"] - 0.1, plot_data["y_max"], "Leading", fontweight="bold", alpha=txt_alpha)
        if plot_data["x_max"] > 100 and plot_data["y_min"] < 100:
            axs.text(plot_data["x_max"] - 0.2, plot_data["y_min"], "Weakening", fontweight="bold", alpha=txt_alpha)
        if plot_data["x_min"] < 100 and plot_data["y_min"] < 100:
            axs.text(plot_data["x_min"] - 0.2, plot_data["y_min"], "Lagging", fontweight="bold", alpha=txt_alpha)

        # Connect event handlers - these might not work seamlessly in Streamlit
        # without further adaptation or specific Streamlit components.
        # For now, the plot will be static in Streamlit unless st.pyplot handles basic interactions.
        self.fig.canvas.mpl_connect("pick_event", self._on_pick)
        self.fig.canvas.mpl_connect("key_press_event", self._on_key_press)

        # Full screen toggle is CLI specific, remove for Streamlit
        # window_manager = plt.get_current_fig_manager()
        # if window_manager: ...

        self.axs = axs
        return self.fig


    @staticmethod
    def _process_ser(ser: pd.Series) -> pd.Series:
        """
        Make corrections in dataframe if there are duplicate indexs
        or not sorted in correct order
        """
        if ser.index.has_duplicates:
            ser = ser.loc[~ser.index.duplicated()]

        if not ser.index.is_monotonic_increasing:
            ser = ser.sort_index(ascending=True)

        return ser

    @staticmethod
    def _get_smooth_curve(x, y):
        # Interpolate a smooth curve through the scatter points
        tck, _ = interpolate.splprep([x, y], s=0, k=2)  # s=0 for no smoothing
        t = np.linspace(0, 1, 100)  # Parameter values
        line_x, line_y = interpolate.splev(t, tck)  # Evaluate spline
        return line_x, line_y

    @staticmethod
    def _format_coords(x, y):
        """
        A function to format the coordinate string
        """
        return f"RS: {x:.2f}     MOM: {y:.2f}"

    @staticmethod
    def _get_color(x, y):
        if x > 100:
            return "#008217" if y > 100 else "#918000"
        else:
            return "#00749D" if y > 100 else "#E0002B"

    def _calculate_rs(
        self, stock_df: pd.Series, benchmark_df: pd.Series
    ) -> pd.Series:
        """
        Returns the RS ratio as a multiple of standard dev of SMA(RS)

        - Take the difference of RS and SMA(RS).
        - Divide the difference with the standard deviation of SMA(RS)
        - Add 100 to serve as a base value
        """
        rs = (stock_df / benchmark_df) * 100

        rs_sma = rs.rolling(window=self.window)

        return ((rs - rs_sma.mean()) / rs_sma.std(ddof=1)).dropna() + 100

    def _calculate_momentum(self, rs_ratio: pd.Series) -> pd.Series:
        """
        Returns the RS momentum as a multiple of standard deviation of SMA(ROC)

        - Calculate the ROC using the first value as base
        - Take the difference of ROC and SMA(ROC)
        - Divide the difference with the standard deviation of SMA(ROC)
        - Add 100 to serve as a base value
        """

        pos = min(len(rs_ratio), self.period)
        base_rs = rs_ratio.shift(pos)

        # Rate of change (ROC)
        rs_roc = ((rs_ratio / base_rs) - 1) * 100

        roc_sma = rs_roc.rolling(window=self.window)

        return ((rs_roc - roc_sma.mean()) / roc_sma.std(ddof=1)).dropna() + 100

    def _clear_all(self, key):
        """
        Clear all additional markers and text annotations
        """
        updated = False

        for url in self.state:
            line = self.state[url]["line"]

            if line._alpha:
                updated = True
                line.set_alpha(0)
                self.state[url]["markers"].set_alpha(0)
                self.state[url]["annotation"].set_alpha(self.text_alpha_state)

        if self.active_date_labels:
            updated = True
            self._clear_active_date_labels()
            self.highlighted_count = 0
            self.tabbable = 0

        if updated:
            self.fig.canvas.draw_idle()

    def _toggle_text(self, key):
        """
        Toggle text labels on the data points.
        """
        alpha = self.text_alpha if self.text_alpha_state == 0 else 0

        for url in self.state:
            annotation = self.state[url]["annotation"]

            # If a text is already highlighted, skip it
            if annotation._alpha == 1:
                continue

            annotation.set_alpha(alpha)

        self.text_alpha_state = alpha
        self.fig.canvas.draw_idle()

    def _toggle_lines(self, key):
        """
        Toggle tail line visibility
        """

        # if current state of alpha is 0, set alpha to its default value, else 0
        alpha = self.line_alpha if self.line_alpha_state == 0 else 0

        for url in self.state:
            line = self.state[url]["line"]

            # If a line is already highlighted, skip it
            if line._alpha == 1:
                continue

            line.set_alpha(alpha)

        # set the new state
        self.line_alpha_state = alpha
        self.fig.canvas.draw_idle()

    def _toggle_help(self, key):
        """
        Toggle Help text
        """

        if self.help_plt is None:
            self.help_plt = self.axs.text(
                100,
                100,
                self.help_str,
                color="black",
                backgroundcolor="white",
                fontweight="bold",
            )
        else:
            self.help_plt.remove()
            self.help_plt = None

        self.fig.canvas.draw_idle()

    def _cycle_dates(self, key):
        """
        Cycle forward through the tail markers and toggle their visibility.
        Only works, when a marker has been highlighted by left mouse click.
        """
        if not self.tabbable:
            return

        step = -1 if key == "left" else 1

        for url in self.state:
            # Check if the line is visible
            if self.state[url]["line"]._alpha == 1:
                length = len(self.state[url]["dates"])

                # tabindex always starts at 0
                date_label = self.state[url]["dates"][self.tabindex]

                if date_label._alpha == 0:
                    # On first label, if date_label is hidden, make it visible
                    date_label.set_alpha(1)
                    date_label.set_backgroundcolor("white")
                else:
                    # on subsequent labels, first hide all date labels
                    # cycle to next or previous label and set visibility
                    self._clear_active_date_labels()
                    self.tabindex = (self.tabindex + step) % length
                    self.state[url]["dates"][self.tabindex].set_alpha(1)
                    self.state[url]["dates"][self.tabindex].set_backgroundcolor(
                        "white"
                    )

                # track the visible labels, so we can clear them as needed
                self.active_date_labels.append(
                    self.state[url]["dates"][self.tabindex]
                )

        self.fig.canvas.draw_idle()

    def _clear_active_date_labels(self):
        """Hide all date labels"""
        for date_label in self.active_date_labels:
            date_label.set_alpha(0)
            date_label._bbox_patch = None
        self.active_date_labels.clear()

    def _on_pick(self, event):
        """
        Handler for the pick event (when the head marker is clicked).

        Toggle visibility of line, markers and text annotations.
        """
        marker = event.artist

        url = marker.get_url()

        line = self.state[url]["line"]
        markers = self.state[url]["markers"]
        annotation = self.state[url]["annotation"]

        # Reset the tabindex and hide any date labels
        self.tabindex = 0

        if self.active_date_labels:
            self._clear_active_date_labels()

        # toggle visibility of tail markers
        if markers._alpha == 0:
            markers.set_alpha(1)
            self.highlighted_count += 1
            self.tabbable = True
        else:
            markers.set_alpha(0)
            self.highlighted_count -= 1

            if self.highlighted_count == 0:
                self.tabbable = False

        # toggle visibility of tail lines
        if self.line_alpha_state == self.line_alpha:
            # If lines are visible, set the alpha to 1,
            # else set to default visibility.
            line.set_alpha(line._alpha == self.line_alpha or self.line_alpha)
        else:
            line.set_alpha(line._alpha == 0 or 0)

        if self.text_alpha_state == self.text_alpha:
            # If text labels are visible, set the alpha to 1,
            # else set to default visibility
            annotation.set_alpha(
                annotation._alpha == self.text_alpha or self.text_alpha
            )
        else:
            annotation.set_alpha(annotation._alpha == 0 or 0)

        self.fig.canvas.draw_idle()

    def _on_key_press(self, event):
        """
        Handler for the key press event.
        """
        key = event.key

        if key in self.key_handler:
            self.key_handler[key](key)
