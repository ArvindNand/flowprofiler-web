import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import streamlit as st
import io

def calculate_continuous_elapsed_time(df_input, timestamp_col='Timestamp', unit_conversion=1000):
    df = df_input.copy()
    timestamps_ms = pd.to_numeric(df[timestamp_col], errors='coerce').fillna(0)

    continuous_elapsed_ms = []
    cumulative_duration_previous_segments_ms = 0
    segment_start_timestamp_ms = timestamps_ms.iloc[0] 

    for i in range(len(timestamps_ms)):
        current_timestamp_ms = timestamps_ms.iloc[i]

        if i > 0 and current_timestamp_ms < timestamps_ms.iloc[i-1]:
            cumulative_duration_previous_segments_ms += (timestamps_ms.iloc[i-1] - segment_start_timestamp_ms)
            segment_start_timestamp_ms = current_timestamp_ms

        elapsed_in_current_segment_ms = current_timestamp_ms - segment_start_timestamp_ms
        total_elapsed_ms = cumulative_duration_previous_segments_ms + elapsed_in_current_segment_ms
        continuous_elapsed_ms.append(total_elapsed_ms)

    return np.array(continuous_elapsed_ms) / unit_conversion

def create_dashboard_fig(df_raw, filename):
    # 1. Trim Data
    if len(df_raw) > 2000:
        df = df_raw.iloc[1000:-1000].copy()
    else:
        df = df_raw.copy()

    # 2. Process Time
    if 'Timestamp' not in df.columns:
        raise ValueError("Error: Column 'Timestamp' not found in CSV.")

    df['Elapsed Time (s)'] = calculate_continuous_elapsed_time(df, timestamp_col='Timestamp')
    df['Elapse Time (min)'] = df['Elapsed Time (s)'] / 60

    # 3. Create Plot Layout
    specs = []
    subplot_titles = []
    
    for i in range(1, 13, 3):
        m1, m2, m3 = i, i+1, i+2
        specs.append([{}, {"rowspan": 2}])
        specs.append([{}, None])
        specs.append([{}, {}])
        subplot_titles.extend([
            f"Motor {m1} RPM", f"Motors {m1} & {m2} Current (Avg)",
            f"Motor {m2} RPM", 
            f"Motor {m3} RPM", f"Motor {m3} Current"
        ])

    fig = make_subplots(
        rows=12, cols=2, shared_xaxes='all', vertical_spacing=0.03,
        horizontal_spacing=0.05, specs=specs, subplot_titles=subplot_titles
    )

    fault_dictionary = {
        1: "Code 1: Driver failed",
        2: "Code 2: Motor stalled",
        3: "Code 3: Hall effect sensor failed",
        31: "Code 31: Comm Loss / I2C Bus Corrupted",
        255: "Code 255: Slave Board Offline (I2C Disconnect)"
    }
    
    for i in range(1, 13):
        rpm_col = f'RPM_M{i}'
        fault_col = f'Fault_M{i}'

        if rpm_col in df.columns:
            fig.add_trace(go.Scatter(x=df['Elapse Time (min)'], y=df[rpm_col], name=f'M{i} RPM', line=dict(color='blue', width=1.5), showlegend=False), row=i, col=1)
            if 'Setpoint' in df.columns:
                fig.add_trace(go.Scatter(x=df['Elapse Time (min)'], y=df['Setpoint'], name='Setpoint', line=dict(color='black', dash='dash', width=1), showlegend=(i==1), legendgroup="setpoint"), row=i, col=1)

        if fault_col in df.columns:
            faults_mask = df[fault_col] > 0
            if faults_mask.any():
                df_faults = df[faults_mask].copy()
                df_faults['Hover_Text'] = df_faults[fault_col].map(lambda x: fault_dictionary.get(x, f"Code {x}: Unknown Fault"))
                fig.add_trace(go.Scatter(x=df_faults['Elapse Time (min)'], y=df_faults[rpm_col], mode='markers', marker=dict(symbol='triangle-up', color='red', size=10, line=dict(width=1, color='darkred')), name=f'Fault M{i}', text=df_faults['Hover_Text'], hoverinfo='text+x+y', showlegend=(i==1), legendgroup="fault"), row=i, col=1)

    for group in range(0, 4):
        base = group * 3
        m1, m2, m3 = base + 1, base + 2, base + 3
        amp1_col, amp2_col = f'Amp_M{m1}', f'Amp_M{m2}'
        
        if amp1_col in df.columns and amp2_col in df.columns:
            avg_col = f'Amp_M{m1}_M{m2}_Avg'
            df[avg_col] = (df[amp1_col] + df[amp2_col]) / 2.0
            fig.add_trace(go.Scatter(x=df['Elapse Time (min)'], y=df[avg_col], name=f'M{m1}&M{m2} Current', line=dict(color='green', width=1.5), showlegend=False), row=m1, col=2)
            
            for m in [m1, m2]:
                fault_col = f'Fault_M{m}'
                if fault_col in df.columns:
                    faults_mask = df[fault_col] > 0
                    if faults_mask.any():
                        df_faults = df[faults_mask].copy()
                        df_faults['Hover_Text'] = df_faults[fault_col].map(lambda x: fault_dictionary.get(x, f"Code {x}: Unknown Fault"))
                        fig.add_trace(go.Scatter(x=df_faults['Elapse Time (min)'], y=df_faults[avg_col], mode='markers', marker=dict(symbol='triangle-up', color='red', size=10, line=dict(width=1, color='darkred')), name=f'Fault M{m}', text=df_faults['Hover_Text'], hoverinfo='text+x+y', showlegend=False, legendgroup="fault"), row=m1, col=2)
                        
        amp3_col = f'Amp_M{m3}'
        if amp3_col in df.columns:
            fig.add_trace(go.Scatter(x=df['Elapse Time (min)'], y=df[amp3_col], name=f'M{m3} Current', line=dict(color='green', width=1.5), showlegend=False), row=m3, col=2)
            fault_col = f'Fault_M{m3}'
            if fault_col in df.columns:
                faults_mask = df[fault_col] > 0
                if faults_mask.any():
                    df_faults = df[faults_mask].copy()
                    df_faults['Hover_Text'] = df_faults[fault_col].map(lambda x: fault_dictionary.get(x, f"Code {x}: Unknown Fault"))
                    fig.add_trace(go.Scatter(x=df_faults['Elapse Time (min)'], y=df_faults[amp3_col], mode='markers', marker=dict(symbol='triangle-up', color='red', size=10, line=dict(width=1, color='darkred')), name=f'Fault M{m3}', text=df_faults['Hover_Text'], hoverinfo='text+x+y', showlegend=False, legendgroup="fault"), row=m3, col=2)

    fig.update_layout(height=3600, title_text=f"12-Motor FlowProfiler Readout: {filename}", showlegend=True, template="plotly_white", hovermode="closest")
    fig.update_xaxes(showticklabels=True)
    fig.update_xaxes(title_text="Elapse Time (min)", rangeslider=dict(visible=True, thickness=0.03), row=12, col=1)
    fig.update_xaxes(title_text="Elapse Time (min)", rangeslider=dict(visible=True, thickness=0.03), row=12, col=2)

    for i in range(1, 13):
        fig.update_yaxes(title_text="RPM", row=i, col=1)
    for r in [1, 3, 4, 6, 7, 9, 10, 12]:
        fig.update_yaxes(title_text="Amps", row=r, col=2)

    return fig

# ==========================================
# STREAMLIT WEB GUI
# ==========================================
st.set_page_config(page_title="FlowProfiler Dashboard", layout="wide")

st.title("🌊 Motor FlowProfiler Readout")
st.markdown("Upload a CSV file from the FlowProfiler to generate an interactive 12-motor telemetry dashboard.")

# Web File Uploader
uploaded_file = st.file_uploader("Select FlowProfiler CSV File", type=['csv', 'CSV'])

if uploaded_file is not None:
    with st.spinner("Crunching telemetry data..."):
        try:
            # Read directly from the uploaded web file
            df_raw = pd.read_csv(uploaded_file)
            
            # Generate the Plotly Figure
            fig = create_dashboard_fig(df_raw, uploaded_file.name)
            
            # Render the figure perfectly inside the browser
            st.plotly_chart(fig, use_container_width=True)
            
            st.success("Readout generated successfully!")
            
            # NEW: Convert figure to HTML and create a download button
            # We use include_plotlyjs="cdn" so the downloaded file is much smaller 
            # (it grabs the rendering library from the internet rather than embedding all of it).
            html_buffer = io.StringIO()
            fig.write_html(html_buffer, include_plotlyjs="cdn")
            html_str = html_buffer.getvalue()
            
            # Generate a clean filename based on the original upload
            base_name = uploaded_file.name.split('.')[0]
            download_filename = f"{base_name}_flowprofiler_readout.html"
            
            # Show the download button
            st.download_button(
                label="💾 Download Interactive HTML Dashboard",
                data=html_str,
                file_name=download_filename,
                mime="text/html"
            )
            
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")