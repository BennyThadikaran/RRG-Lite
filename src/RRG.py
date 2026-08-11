import sys
from typing import Callable, Dict, Final

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import utils

version = "1.0.12-beta.2"


class RRG:
    def __init__(
        self,
        config: dict,
        watchlist: list,
        tail_count=4,
        benchmark=None,
        **kwargs,
    ):
        self.use_scipy = config.get("SCIPY_INSTALLED", False)
        self.interpolate_fn = None

        if self.use_scipy:
            try:
                from scipy import interpolate

                self.interpolate_fn = interpolate
            except ModuleNotFoundError:
                print(
                    "Module scipy is not installed. Run `pip install scipy` to install it."
                )
                exit(1)

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

        self.window = config.get("WINDOW", 14)
        self.period = config.get("PERIOD", 52)
        self.base_date = config.get("BASE_DATE")
        self.config = config
        self.base_rs = None

        # Keep track of data points, lines and text annotations
        self.state = {}

        # Keep track of the alpha state of lines and text
        self.text_alpha_state = 0
        self.line_alpha_state = 0

        # Default alpha values for lines and text
        self.text_alpha = 0.6
        self.line_alpha = 0.5

        # 2x Window periods for moving averages (RS & ROC)
        # + Additional period for ROC base period calculation
        # + tail count
        self.minimum_data_length = (
            self.window * 2 + max(self.window, self.period) + self.tail_count
        )

        loader_class = utils.get_loader_class(config)

        self.loader = loader_class(config, period=self.minimum_data_length, **kwargs)

        self.help_plt = None

        self.help_str = """
KEYBOARD SHORTCUTS
────────────────────────────────

Del        Clear all lines and annotations; exit tail mode
A          Toggle text annotations
T          Toggle tail lines
Shift+T    Toggle tail mode
H          Show / hide this help

TAIL MODE
────────────────────────────────

1. Left-click a marker or press Shift+T to enter tail mode.
2. Use ↑ and ↓ to cycle through markers.
3. Use ← and → to cycle through dates.
4. Press Shift+T or Del, or click the active marker, to exit.
"""

        # Map keyboard shortcuts to their relevant handlers
        self.key_handler: Final[Dict[str, Callable]] = {
            "delete": self._clear_all,
            "a": self._toggle_text,
            "t": self._toggle_lines,
            "shift+t": self._toggle_tail_mode,
            "h": self._toggle_help,
            "left": self._cycle_dates,
            "right": self._cycle_dates,
            "up": self._cycle_markers,
            "down": self._cycle_markers,
        }

        # Tail-mode state. Only one marker can be active at a time.
        self.tail_mode = False
        self.active_marker_url = None
        self.active_marker_index = 0

        # Track the date label selected for the active marker.
        self.tabindex = 0
        self.active_date_labels = []

    def plot(self):
        txt_alpha = 0.4

        # colors = np.random.rand(len(self.watchlist), 3) * 0.6

        bm = self.loader.get(self.benchmark)

        if bm is None or bm.empty:
            raise ValueError(f"Unable to load benchmark data for {self.benchmark}")

        if len(bm) < self.minimum_data_length:
            raise ValueError("Benchmark data is insufficient to plot chart.")

        bm_closes = self._process_ser(bm.loc[:, "Close"])

        # Setup the chart
        fig, axs = plt.subplots()

        self.fig = fig
        self.axs = axs
        axs.format_coord = self._format_coords

        plt.tight_layout()

        axs.set_title(f"RRG - {self.benchmark.upper()} - {bm.index[-1]:%d %b %Y}")
        axs.set_xlabel("RS Ratio")
        axs.set_ylabel("RS Momentum")

        # Center line that divided the quadrant
        axs.axhline(y=100, color="black", linestyle="--", linewidth=0.3)
        axs.axvline(x=100, color="black", linestyle="--", linewidth=0.3)

        x_max = y_max = 0
        x_min = y_min = 200

        # Start calculation of RS and RS Momentum
        for i, ticker in enumerate(self.watchlist):
            short_name = None

            ticker, _, short_name = ticker.partition(",")

            if not short_name:
                short_name = ticker

            df = self.loader.get(ticker)

            if df is None or df.empty:
                continue

            ser_closes = self._process_ser(df.loc[:, "Close"])

            rsr = self._calculate_rs(ser_closes, bm_closes)

            rsm = self._calculate_momentum(rsr, ticker)

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
                zorder=10,
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
                zorder=10,
            )

            if self.tail_count > 2:
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
                visible=False,
            )

        x_lim_min = x_min - 0.3
        x_lim_max = x_max + 0.3
        y_lim_min = y_min - 0.3
        y_lim_max = y_max + 0.3

        axs.set_title(
            "h → Toggle Help",
            loc="left",
            color="darkslategray",
            fontname="monospace",
        )

        # Background colors for each quadrant
        axs.fill_between([x_lim_min, 100], 100, y_lim_max, color="#b1ebff")
        axs.fill_between([100, x_lim_max], 100, y_lim_max, color="#bdffc9")
        axs.fill_between([100, x_lim_max], y_lim_min, 100, color="#fff7b8")
        axs.fill_between([x_lim_min, 100], y_lim_min, 100, color="#ffb9c6")

        axs.set_xlim(x_lim_min, x_lim_max)
        axs.set_ylim(y_lim_min, y_lim_max)

        # Labels for each quadrant
        label_pad = 0.03

        if x_min < 100 and y_max > 100:
            axs.text(
                label_pad,
                1 - label_pad,
                "Improving",
                fontweight="bold",
                alpha=txt_alpha,
                transform=axs.transAxes,
                ha="left",
                va="top",
            )

        if x_max > 100 and y_max > 100:
            axs.text(
                1 - label_pad,
                1 - label_pad,
                "Leading",
                fontweight="bold",
                alpha=txt_alpha,
                transform=axs.transAxes,
                ha="right",
                va="top",
            )

        if x_max > 100 and y_min < 100:
            axs.text(
                1 - label_pad,
                label_pad,
                "Weakening",
                fontweight="bold",
                alpha=txt_alpha,
                transform=axs.transAxes,
                ha="right",
                va="bottom",
            )

        if x_min < 100 and y_min < 100:
            axs.text(
                label_pad,
                label_pad,
                "Lagging",
                fontweight="bold",
                alpha=txt_alpha,
                transform=axs.transAxes,
                ha="left",
                va="bottom",
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

        plt.show()

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

    def _get_smooth_curve(self, x, y, samples=100):
        """Interpolate a smooth curve through the scatter points"""
        if self.use_scipy and self.interpolate_fn is not None:
            tck, _ = self.interpolate_fn.splprep(
                [x, y],
                s=0,  # s=0 for no smoothing
                k=2,
            )
            t = np.linspace(0, 1, 100)
            line_x, line_y = self.interpolate_fn.splev(t, tck)
            return line_x, line_y

        # Create a smooth curve through x/y points using a Catmull-Rom spline.
        # Numpy only implementation
        points = np.column_stack(
            (
                np.asarray(x, dtype=float),
                np.asarray(y, dtype=float),
            )
        )

        point_count = len(points)

        # Duplicate the endpoints so the curve starts and ends at the
        # first and last supplied points.
        padded = np.vstack((points[0], points, points[-1]))

        # Map the requested samples across all spline segments.
        position = np.linspace(0.0, point_count - 1, samples)
        segment = np.minimum(position.astype(int), point_count - 2)
        t = position - segment

        p0 = padded[segment]
        p1 = padded[segment + 1]
        p2 = padded[segment + 2]
        p3 = padded[segment + 3]

        t = t[:, None]
        t2 = t * t
        t3 = t2 * t

        # Standard formula for Catmull–Rom splines
        curve = 0.5 * (
            2.0 * p1
            + (-p0 + p2) * t
            + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
            + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3
        )

        return curve[:, 0], curve[:, 1]

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

    def _calculate_rs(self, stock_df: pd.Series, benchmark_df: pd.Series) -> pd.Series:
        """
        Returns the RS ratio as a multiple of standard dev of SMA(RS)

        - Take the difference of RS and SMA(RS).
        - Divide the difference with the standard deviation of SMA(RS)
        - Add 100 to serve as a base value
        """
        rs = (stock_df / benchmark_df) * 100

        rs_sma = rs.rolling(window=self.window)

        return ((rs - rs_sma.mean()) / rs_sma.std(ddof=1)).dropna() + 100

    def _calculate_momentum(self, rs_ratio: pd.Series, ticker: str) -> pd.Series:
        """
        Returns the RS momentum as a multiple of standard deviation of SMA(ROC)

        - Calculate the ROC using the first value as base
        - Take the difference of ROC and SMA(ROC)
        - Divide the difference with the standard deviation of SMA(ROC)
        - Add 100 to serve as a base value
        """
        if self.base_date and self.base_rs is not None:
            # use NEXT index value if no exact match
            position = rs_ratio.index.get_indexer(
                [self.base_date],
                method="bfill",
                tolerance=pd.Timedelta(days=6),
            )[0]

            if position == -1:
                # No index date exists after base_date
                self.base_rs = rs_ratio.iloc[-self.period]
                print(
                    f"{ticker}: Could not find base_date. Falling back to RS value {self.period} periods ago."
                )
            else:
                self.base_rs = rs_ratio.iloc[position]
        else:
            self.base_rs = rs_ratio.iloc[-self.period]

        # Rate of change (ROC)
        rs_roc = ((rs_ratio / self.base_rs) - 1) * 100

        roc_sma = rs_roc.rolling(window=self.window)

        return ((rs_roc - roc_sma.mean()) / roc_sma.std(ddof=1)).dropna() + 100

    def _clear_all(self, key):
        """
        Clear all additional markers and text annotations and exit tail mode.
        """
        updated = self.tail_mode or bool(self.active_date_labels)

        self._exit_tail_mode(draw=False)

        for url in self.state:
            if self.state[url]["visible"]:
                updated = True
                self.state[url]["visible"] = False

                line = self.state[url]["line"]
                markers = self.state[url]["markers"]
                annotation = self.state[url]["annotation"]

                line.set_alpha(0)
                markers.set_alpha(0)
                annotation.set_alpha(0)

        self.line_alpha_state = 0
        self.text_alpha_state = 0

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

            self.state[url]["visible"] = True
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
                0.03,
                0.97,
                self.help_str,
                transform=self.axs.transAxes,
                ha="left",
                va="top",
                fontsize=11,
                family="monospace",
                color="#222222",
                linespacing=1.4,
                bbox=dict(
                    boxstyle="round,pad=0.8",
                    facecolor="white",
                    edgecolor="#BBBBBB",
                    linewidth=1.5,
                ),
                zorder=200,
            )

        else:
            self.help_plt.remove()
            self.help_plt = None

        self.fig.canvas.draw_idle()

    def _toggle_tail_mode(self, key):
        """Enter or exit tail mode."""
        if self.tail_mode:
            self._exit_tail_mode()
            return

        marker_urls = list(self.state)

        if not marker_urls:
            return

        # Keep index between 0 and len(marker_urls)
        self.active_marker_index %= len(marker_urls)

        self._activate_marker(marker_urls[self.active_marker_index])

    def _activate_marker(self, url, draw=True):
        """Activate one marker and restore any previously active marker."""
        if url not in self.state:
            return

        if self.active_marker_url and self.active_marker_url != url:
            self._restore_marker(self.active_marker_url)

        self._clear_active_date_labels()
        self.tabindex = 0

        marker_urls = list(self.state)
        self.active_marker_index = marker_urls.index(url)
        self.active_marker_url = url
        self.tail_mode = True
        self._update_mode()

        item = self.state[url]
        item["line"].set_alpha(1)
        item["markers"].set_alpha(1)
        item["annotation"].set_alpha(1)
        item["visible"] = True

        if draw:
            self.fig.canvas.draw_idle()

    def _restore_marker(self, url):
        """Restore a marker to the current global line/text visibility state."""
        if url not in self.state:
            return

        item = self.state[url]
        item["line"].set_alpha(self.line_alpha_state)
        item["markers"].set_alpha(0)
        item["annotation"].set_alpha(self.text_alpha_state)

    def _exit_tail_mode(self, draw=True):
        """Exit tail mode and restore the active marker's normal appearance."""
        self._clear_active_date_labels()

        if self.active_marker_url:
            self._restore_marker(self.active_marker_url)

        self.tail_mode = False
        self.active_marker_url = None
        self.tabindex = 0
        self._update_mode()

        if draw:
            self.fig.canvas.draw_idle()

    def _cycle_markers(self, key):
        """Cycle through head markers while tail mode is active."""
        if not self.tail_mode or not self.state:
            return

        marker_urls = list(self.state)
        step = -1 if key == "up" else 1
        self.active_marker_index = (self.active_marker_index + step) % len(marker_urls)
        self._activate_marker(marker_urls[self.active_marker_index])

    def _cycle_dates(self, key):
        """
        Cycle through the active marker's date labels while in tail mode.
        """
        if not self.tail_mode or self.active_marker_url is None:
            return

        step = -1 if key == "left" else 1
        dates = self.state[self.active_marker_url]["dates"]

        if not dates:
            return

        date_label = dates[self.tabindex]

        if date_label._alpha == 0:
            # The first arrow press displays the initial date label.
            date_label.set_alpha(1)
            date_label.set_backgroundcolor("white")
        else:
            self._clear_active_date_labels()
            self.tabindex = (self.tabindex + step) % len(dates)
            date_label = dates[self.tabindex]
            date_label.set_alpha(1)
            date_label.set_backgroundcolor("white")

        self.active_date_labels.append(date_label)

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

        Enter tail mode for the clicked marker, select a different marker,
        or exit when the active marker is clicked again.
        """
        marker = event.artist

        url = marker.get_url()

        if url not in self.state:
            return

        if self.tail_mode and self.active_marker_url == url:
            self._exit_tail_mode()
        else:
            self._activate_marker(url)

    def _on_key_press(self, event):
        """
        Handler for the key press event.
        """
        key = event.key

        if key in {"T", "shift+t", "shift+T"}:
            key = "shift+t"
        elif isinstance(key, str) and len(key) == 1:
            key = key.lower()

        if key in self.key_handler:
            self.key_handler[key](key)

    def _update_mode(self):
        label = "Tail Mode On" if self.tail_mode else ""
        self.axs.set_title(
            label,
            loc="right",
            color="darkslategray",
            fontname="monospace",
        )
