from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st


DATA_PATH = Path("data/signal_samples.csv")
REQUIRED_COLUMNS = [
    "Latitude",
    "Longitude",
    "CellID",
    "Band",
    "RSRP_dBm",
    "SINR_dB",
    "TerminalType",
    "Download_Mbps",
]


# Core data loading function. Kept separate from Streamlit UI so it can be unit tested.
def read_signal_data(csv_path: Path | str = DATA_PATH) -> pd.DataFrame:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV data file not found: {path}")

    df = pd.read_csv(path)
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing_columns)}")

    numeric_columns = ["Latitude", "Longitude", "RSRP_dBm", "SINR_dB", "Download_Mbps"]
    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


@st.cache_data
def load_signal_data(csv_path: str = str(DATA_PATH)) -> pd.DataFrame:
    return read_signal_data(csv_path)


# Hex color mapping used by st.map. Includes pd.isna() guard for missing/non-numeric RSRP.
def rsrp_to_hex(value: object) -> str:
    numeric_value = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric_value):
        return "#888888"
    if numeric_value > -90:
        return "#00FF00"
    if -110 <= numeric_value <= -90:
        return "#FFFF00"
    return "#FF0000"


# RGB color mapping used by pydeck ColumnLayer. Same thresholds as hex mapping.
def rsrp_to_rgb(value: object) -> list[int]:
    numeric_value = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric_value):
        return [128, 128, 128]
    if numeric_value > -90:
        return [0, 255, 0]
    if -110 <= numeric_value <= -90:
        return [255, 255, 0]
    return [255, 0, 0]


# Shared filtering logic for sidebar controls and unit tests.
def filter_signal_data(
    df: pd.DataFrame,
    selected_bands: list[str],
    rsrp_range: tuple[float, float] | list[float],
) -> pd.DataFrame:
    rsrp_values = pd.to_numeric(df["RSRP_dBm"], errors="coerce")
    band_mask = df["Band"].isin(selected_bands) if selected_bands else pd.Series(False, index=df.index)
    rsrp_mask = rsrp_values.between(rsrp_range[0], rsrp_range[1], inclusive="both")
    return df.loc[band_mask & rsrp_mask].copy()


def add_visual_columns(df: pd.DataFrame) -> pd.DataFrame:
    visual_df = df.copy()
    visual_df["color_hex"] = visual_df["RSRP_dBm"].apply(rsrp_to_hex)
    visual_df["color_rgb"] = visual_df["RSRP_dBm"].apply(rsrp_to_rgb)

    max_download = pd.to_numeric(visual_df["Download_Mbps"], errors="coerce").max()
    if pd.isna(max_download) or max_download <= 0:
        visual_df["elevation"] = 0.0
    else:
        visual_df["elevation"] = (
            pd.to_numeric(visual_df["Download_Mbps"], errors="coerce").fillna(0) / max_download
        ) * 2000

    return visual_df


def render_sidebar_filters(df: pd.DataFrame) -> tuple[list[str], tuple[int, int]]:
    st.sidebar.header("筛选器")

    # Frequency band filter. Options come from data and default to all bands.
    band_options = sorted(df["Band"].dropna().astype(str).unique().tolist())
    selected_bands = st.sidebar.multiselect(
        "频段选择器",
        options=band_options,
        default=band_options,
    )

    rsrp_numeric = pd.to_numeric(df["RSRP_dBm"], errors="coerce")
    rsrp_min = int(np.floor(rsrp_numeric.min())) if rsrp_numeric.notna().any() else -140
    rsrp_max = int(np.ceil(rsrp_numeric.max())) if rsrp_numeric.notna().any() else -40

    # RSRP range filter with 1 dBm step.
    selected_rsrp_range = st.sidebar.slider(
        "RSRP 范围 (dBm)",
        min_value=rsrp_min,
        max_value=rsrp_max,
        value=(rsrp_min, rsrp_max),
        step=1,
    )

    return selected_bands, selected_rsrp_range


def render_map(filtered_df: pd.DataFrame) -> None:
    st.subheader("交互式信号地图")
    if filtered_df.empty:
        st.warning("当前筛选条件下没有可展示的采样点。")
        return

    map_df = filtered_df.dropna(subset=["Latitude", "Longitude"]).copy()
    if map_df.empty:
        st.warning("当前筛选结果缺少有效经纬度，无法绘制地图。")
        return

    st.map(
        map_df,
        latitude="Latitude",
        longitude="Longitude",
        color="color_hex",
        size=35,
        zoom=11,
    )


def render_summary_charts(filtered_df: pd.DataFrame) -> None:
    left_col, right_col = st.columns(2)

    # Plotly bar chart: record counts by 5G band.
    with left_col:
        st.subheader("各频段基站数量")
        if filtered_df.empty:
            st.info("无数据可绘制柱状图。")
        else:
            band_counts = (
                filtered_df.groupby("Band", dropna=False)
                .size()
                .reset_index(name="记录数")
                .sort_values("记录数", ascending=False)
            )
            fig_bar = px.bar(
                band_counts,
                x="Band",
                y="记录数",
                text="记录数",
                color="Band",
            )
            fig_bar.update_layout(showlegend=False, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_bar, width="stretch")

    # Plotly pie chart: terminal type distribution.
    with right_col:
        st.subheader("终端类型占比")
        if filtered_df.empty:
            st.info("无数据可绘制饼图。")
        else:
            fig_pie = px.pie(
                filtered_df,
                names="TerminalType",
                hole=0.35,
            )
            fig_pie.update_traces(textposition="inside", textinfo="percent+label")
            fig_pie.update_layout(margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_pie, width="stretch")


def render_3d_columns(filtered_df: pd.DataFrame) -> None:
    st.subheader("🏗️ 3D 信号柱状图")
    if filtered_df.empty:
        st.warning("当前筛选条件下没有可展示的 3D 柱状图数据。")
        return

    deck_df = filtered_df.dropna(subset=["Latitude", "Longitude"]).copy()
    if deck_df.empty:
        st.warning("当前筛选结果缺少有效经纬度，无法绘制 3D 视图。")
        return

    center_latitude = deck_df["Latitude"].mean()
    center_longitude = deck_df["Longitude"].mean()

    column_layer = pdk.Layer(
        "ColumnLayer",
        data=deck_df,
        get_position=["Longitude", "Latitude"],
        get_elevation="elevation",
        elevation_scale=1,
        radius=80,
        get_fill_color="color_rgb",
        pickable=True,
        auto_highlight=True,
    )

    view_state = pdk.ViewState(
        latitude=center_latitude,
        longitude=center_longitude,
        zoom=11,
        pitch=50,
        bearing=20,
    )

    tooltip = {
        "html": (
            "<b>CellID:</b> {CellID}<br/>"
            "<b>Band:</b> {Band}<br/>"
            "<b>RSRP:</b> {RSRP_dBm} dBm<br/>"
            "<b>Download:</b> {Download_Mbps} Mbps"
        ),
        "style": {"backgroundColor": "#1f2937", "color": "white"},
    }

    st.pydeck_chart(
        pdk.Deck(
            layers=[column_layer],
            initial_view_state=view_state,
            map_style=pdk.map_styles.CARTO_LIGHT,
            tooltip=tooltip,
        ),
        width="stretch",
    )


def main() -> None:
    st.set_page_config(page_title="📡 5G 信号可视化看板", layout="wide")
    st.title("📡 5G 信号可视化看板")

    if not DATA_PATH.exists():
        st.error(f"未找到数据文件：{DATA_PATH}。请将 CSV 放置在 data/signal_samples.csv。")
        st.stop()

    try:
        df = load_signal_data(str(DATA_PATH))
    except Exception as exc:
        st.error(f"数据加载失败：{exc}")
        st.stop()

    selected_bands, selected_rsrp_range = render_sidebar_filters(df)
    filtered_df = filter_signal_data(df, selected_bands, selected_rsrp_range)
    filtered_df = add_visual_columns(filtered_df)

    metric_cols = st.columns(4)
    metric_cols[0].metric("采样点", f"{len(filtered_df):,}")
    metric_cols[1].metric("频段数", f"{filtered_df['Band'].nunique():,}" if not filtered_df.empty else "0")
    metric_cols[2].metric(
        "平均 RSRP",
        f"{filtered_df['RSRP_dBm'].mean():.1f} dBm" if not filtered_df.empty else "N/A",
    )
    metric_cols[3].metric(
        "平均下载速率",
        f"{filtered_df['Download_Mbps'].mean():.1f} Mbps" if not filtered_df.empty else "N/A",
    )

    render_map(filtered_df)
    render_summary_charts(filtered_df)
    render_3d_columns(filtered_df)


if __name__ == "__main__":
    main()
