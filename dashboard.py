import streamlit as st
import sys
from pathlib import Path
import matplotlib.pyplot as plt
from datetime import datetime

# --- Setup Python Path ---
# Add the 'src' directory to sys.path to allow direct imports of modules like 'utils' and 'RRG'.
# This assumes dashboard.py is in the project root directory alongside the 'src' folder.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from utils import load_config #, get_loader_class (get_loader_class is used within RRG)
from RRG import RRG

# --- Page Configuration ---
st.set_page_config(layout="wide")
st.title("RRG Lite Dashboard")

# --- Configuration Loading ---
# Attempt to load 'user.json' configuration file.
# Tries to find it assuming dashboard.py is in project root, then tries as if dashboard.py is in src.
# This makes it flexible for different execution contexts.
def find_config_file():
    """Attempts to locate the user.json config file."""
    base_path = Path(__file__).resolve().parent
    # Path if dashboard.py is in project root
    config_path_root = base_path / "src" / "user.json"
    # Path if dashboard.py is in src/ (less likely for this script name)
    config_path_src = base_path / "user.json"
    # Path if CWD is project root (e.g. streamlit run dashboard.py from root)
    config_path_cwd_src = Path.cwd() / "src" / "user.json"

    if config_path_root.exists():
        return config_path_root
    if config_path_src.exists(): # if dashboard.py is in src/
        return config_path_src
    if config_path_cwd_src.exists(): # if running from project root and dashboard.py is also there
         return config_path_cwd_src
    return None

config_file = find_config_file()

if not config_file:
    st.error(f"Configuration file (user.json) not found. Please ensure it's in the 'src' directory.")
    st.stop()

config = load_config(str(config_file))

if not config:
    st.error(f"Failed to load configuration from {config_file}. Check its format and content.")
    st.stop()

# Validate and resolve DATA_PATH from the configuration.
# DATA_PATH is crucial for loading stock/benchmark CSV files.
data_path_str = config.get("DATA_PATH", "")
if not data_path_str:
    st.error("`DATA_PATH` not specified in the configuration file (user.json).")
    st.stop()

data_path = Path(data_path_str).expanduser()
if not data_path.is_absolute():
    # If DATA_PATH is relative, resolve it with respect to the *config file's directory*.
    data_path = (config_file.parent / data_path_str).resolve()

if not data_path.is_dir():
    st.error(f"`DATA_PATH` ('{config.get('DATA_PATH')}') is not a valid directory. Resolved to: {data_path}")
    st.stop()
config["DATA_PATH"] = str(data_path) # Store the resolved, absolute path back in config for RRG module

# --- Sidebar UI for Inputs ---
st.sidebar.header("RRG Inputs")

# Benchmark Symbol Input
DEFAULT_BENCHMARK = config.get("BENCHMARK", "nifty 50") # Default from user.json or a common index
benchmark_symbol = st.sidebar.text_input("Benchmark Symbol", value=DEFAULT_BENCHMARK)
st.sidebar.caption("Enter symbol name without .csv extension (e.g., 'nifty 50').")

st.sidebar.markdown("---")

# Watchlist Input Method (Text Area or File Upload)
st.sidebar.subheader("Watchlist Input")
watchlist_option = st.sidebar.radio("Choose watchlist input method:", ("Text Area", "File Upload"), index=0)

DEFAULT_WATCHLIST_STR = "reliance,tcs,infosys,hdfcbank" # Common example symbols
watchlist_str = ""
uploaded_watchlist_file = None

if watchlist_option == "Text Area":
    watchlist_str = st.sidebar.text_area("Symbols (comma-separated)", value=DEFAULT_WATCHLIST_STR, height=100)
    st.sidebar.caption("Enter symbol names without .csv extension.")
else:
    uploaded_watchlist_file = st.sidebar.file_uploader("Upload Watchlist File", type=["txt", "csv"])
    st.sidebar.caption("File should contain one symbol per line (without .csv extension).")

st.sidebar.markdown("---")

# RRG Specific Parameters
st.sidebar.subheader("RRG Parameters")
DEFAULT_TAIL_COUNT = config.get("TAIL_COUNT", 4) # Default from user.json or common value
tail_count = st.sidebar.slider("Tail Length (periods)", min_value=2, max_value=20, value=DEFAULT_TAIL_COUNT)

DEFAULT_TIMEFRAME = config.get("DEFAULT_TF", "weekly") # Default from user.json
timeframe_options = ["daily", "weekly", "monthly", "quarterly"]
timeframe_default_index = timeframe_options.index(DEFAULT_TIMEFRAME) if DEFAULT_TIMEFRAME in timeframe_options else 1 # Default to weekly if not found
timeframe = st.sidebar.selectbox("Timeframe",
                                 options=timeframe_options,
                                 index=timeframe_default_index)

default_window = config.get("WINDOW", 14) # RSR rolling window
default_period = config.get("PERIOD", 52) # RSM lookback period
rrg_window = st.sidebar.number_input("RS-Ratio Window (periods)", min_value=5, max_value=100, value=default_window)
rrg_period = st.sidebar.number_input("RS-Momentum Period (lookback)", min_value=10, max_value=200, value=default_period)

selected_end_date = st.sidebar.date_input("End Date for Analysis", value=datetime.today())
# RRG module expects datetime object, st.date_input provides datetime.date, so combine with min time.
end_date_dt = datetime.combine(selected_end_date, datetime.min.time())

st.sidebar.markdown("---")

# Display Configuration Info
st.sidebar.subheader("Configuration Info")
st.sidebar.caption(f"Data Path: {config.get('DATA_PATH')}")
st.sidebar.caption(f"Config File: {config_file}")


# --- Main Panel: Chart Generation and Display ---
if st.sidebar.button("Generate RRG Chart"):
    # Process watchlist based on selected input method
    watchlist = []
    if uploaded_watchlist_file:
        try:
            watchlist_content = uploaded_watchlist_file.read().decode().strip()
            watchlist = [line.strip() for line in watchlist_content.splitlines() if line.strip() and not line.startswith('#')] # Ignore empty lines and comments
            if watchlist:
                 st.sidebar.success(f"Loaded {len(watchlist)} symbols from file.")
            else:
                st.sidebar.error("No valid symbols found in the uploaded file.")
                st.stop()
        except Exception as e:
            st.sidebar.error(f"Error reading watchlist file: {e}")
            st.stop()
    elif watchlist_str:
        watchlist = [s.strip() for s in watchlist_str.split(',') if s.strip()]

    # Validate essential inputs
    if not benchmark_symbol:
        st.error("Benchmark symbol cannot be empty.")
        st.stop()
    if not watchlist:
        st.error("Watchlist cannot be empty. Please enter symbols or upload a file.")
        st.stop()

    # Enclose RRG generation in a try-except block to catch errors from the RRG module
    try:
        # Instantiate the RRG class with parameters from the UI
        rrg_instance = RRG(
            config=config,              # Loaded user configuration
            watchlist=watchlist,        # List of symbols
            tail_count=tail_count,      # Length of the tail on the chart
            benchmark=benchmark_symbol, # Benchmark symbol name
            tf=timeframe,               # Timeframe for data (daily, weekly, etc.)
            end_date=end_date_dt,       # End date for data analysis
            window=rrg_window,          # Rolling window for RS-Ratio calculation
            period=rrg_period           # Lookback period for RS-Momentum calculation
        )

        # Display summary of parameters being used
        st.subheader("Chart Generation Parameters")
        param_summary = (
            f"- **Benchmark:** {benchmark_symbol.upper()}\n"
            f"- **Symbols:** {', '.join(s.upper() for s in watchlist)}\n"
            f"- **Timeframe:** {timeframe}\n"
            f"- **Tail Length:** {tail_count}\n"
            f"- **RS-Ratio Window:** {rrg_window}\n"
            f"- **RS-Momentum Period:** {rrg_period}\n"
            f"- **End Date:** {selected_end_date.strftime('%Y-%m-%d')}"
        )
        st.markdown(param_summary)

        # Step 1: Prepare RRG data (calculations)
        with st.spinner("Calculating RRG data... This may take a moment for large watchlists or long histories."):
            rrg_plot_data = rrg_instance.prepare_rrg_data()

        # Step 2: Generate Matplotlib figure
        with st.spinner("Generating chart figure..."):
            fig = rrg_instance.generate_rrg_figure(rrg_plot_data)

        # Display any warnings collected during data preparation
        if rrg_plot_data.get("warnings"):
            st.warning("⚠️ Issues encountered during data processing (chart may be partial or some symbols skipped):")
            for warning_msg in rrg_plot_data["warnings"]:
                st.markdown(f"  - {warning_msg}")

        # Display the chart in Streamlit
        if not fig:
            st.error("Chart could not be generated. This might happen if data preparation failed unexpectedly after initial checks.")
        elif not rrg_plot_data["tickers_data"]: # No tickers made it to the plot
             st.error("🚫 No valid ticker data available to plot after processing. Please check your symbols, data files, and selected date range.")
        else:
            st.pyplot(fig) # Display the Matplotlib figure
            st.success("✅ RRG Chart generated successfully!")

    except ValueError as ve: # Catch errors raised by RRG module (e.g., benchmark not found)
        st.error(f"🚫 ValueError during RRG generation: {ve}")
        if 'rrg_plot_data' in locals() and rrg_plot_data and rrg_plot_data.get("warnings"):
            st.warning("Additionally, the following issues were noted before the error occurred:")
            for warning_msg in rrg_plot_data["warnings"]:
                st.markdown(f"- {warning_msg}")
    except FileNotFoundError as fnf: # Catch file access errors
        st.error(f"🚫 FileNotFoundError: {fnf}. Please ensure `DATA_PATH` in `user.json` is correct and all CSV files exist.")
    except Exception as e: # Catch any other unexpected errors
        st.error(f"🚫 An unexpected error occurred: {e}")
        import traceback
        st.error("Full Traceback:")
        st.text(traceback.format_exc()) # Display full traceback for debugging

else:
    # Initial message when the app loads
    st.info("Adjust parameters in the sidebar and click 'Generate RRG Chart' to display the graph.")

# --- Footer/Instructions ---
st.markdown("---")
st.markdown("""
**Instructions for Use:**
1.  Ensure you have a `user.json` file in the `src` directory.
2.  This `user.json` must specify `DATA_PATH` pointing to your folder of OHLC CSV data.
    Example `user.json`:
    ```json
    {
      "DATA_PATH": "full/path/to/your/ohlc_csv_data/",
      "BENCHMARK": "nifty 50",
      "DEFAULT_TF": "weekly",
      "WINDOW": 14,
      "PERIOD": 52
    }
    ```
3.  Symbol CSV files should be named `symbolname.csv` (e.g., `reliance.csv`).
4.  Adjust parameters in the sidebar and click "Generate RRG Chart".

**To run the dashboard:** `streamlit run dashboard.py` (from the project root directory)
""")
