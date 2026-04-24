import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Hardware Eng Services", layout="wide")

@st.cache_data
def load_data():
    projects = pd.read_csv("Final_Projects_Data.csv")
    vendors = pd.read_csv("Final_Vendors_Data.csv")
    
    # Identify slip severity for the hardware/nuclear side
    def evaluate_slip(row):
        if row['Schedule Delay (Days)'] == 0:
            return "On Track"
        elif row['Schedule Delay (Days)'] <= row['Available Float (Days)']:
            return "Slip (Within Float)"
        else:
            return "CRITICAL PATH IMPACT"
            
    projects['Slip Status'] = projects.apply(evaluate_slip, axis=1)
    
    # Rollup vendor metrics for the Risk Matrix
    vendor_metrics = projects.groupby('External Firm(s)').agg({
        'Schedule Delay (Days)': 'mean',
        'First-Pass Yield (%)': 'mean'
    }).reset_index()
    vendors = pd.merge(vendors, vendor_metrics, left_on='Firm', right_on='External Firm(s)', how='left')
    
    return projects, vendors

projects_df, vendors_df = load_data()

st.title("External Engineering Services Command Center")
st.markdown("Executive overview of vendor health, quality, and programmatic schedule risk.")

# --- Executive KPIs ---
c1, c2, c3, c4 = st.columns(4)
c1.metric("Portfolio Cost Variance", f"${projects_df['Cost Variance (CV)'].sum():,.0f}")
c2.metric("Portfolio Avg Quality (FPY)", f"{projects_df['First-Pass Yield (%)'].mean():.1f}%")
critical_slips = len(projects_df[projects_df['Slip Status'] == 'CRITICAL PATH IMPACT'])
c3.metric("Critical Path Breaches", critical_slips, delta="High Risk", delta_color="inverse")
c4.metric("Hardware Non-Conformances", projects_df['NCR / SDR Count'].sum())

st.markdown("---")

# --- Main Dash ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("Vendor Health Matrix (Quality vs. Delivery)")
    st.markdown("High-level executive view of current vendor risk profiles.")
    
    fig_scatter = px.scatter(
        vendors_df, 
        x="Schedule Delay (Days)", 
        y="First-Pass Yield (%)", 
        size="Active SOWs",
        hover_name="Firm",
        text="Firm_Stacked",
        color="Avg First-Pass Yield (%)",
        color_continuous_scale="RdYlGn"
    )
    fig_scatter.update_traces(
        textposition='top center',
        textfont=dict(size=12, color="white"),
        cliponaxis=False # Prevents labels near the edge from being cut off
    )
    fig_scatter.add_hline(y=80, line_dash="dot", annotation_text="Quality Target (80%)", annotation_position="bottom right")
    fig_scatter.add_vline(x=30, line_dash="dot", annotation_text="Delay Threshold (30 Days)", annotation_position="top right")
    
    # Pad the axes slightly so the stacked text has room to breathe
    x_max = vendors_df["Schedule Delay (Days)"].max() if pd.notna(vendors_df["Schedule Delay (Days)"].max()) else 30
    y_max = vendors_df["First-Pass Yield (%)"].max() if pd.notna(vendors_df["First-Pass Yield (%)"].max()) else 90
    
    fig_scatter.update_layout(
        xaxis_title="Avg Schedule Delay (Days)", 
        yaxis_title="First-Pass Yield / Acceptance Rate (%)",
        xaxis=dict(range=[-5, max(x_max + 10, 40)]), 
        yaxis=dict(range=[65, max(y_max + 5, 100)]),
        height=450
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

with col2:
    st.subheader("Programmatic Schedule Risk (Slip vs. Float)")
    st.markdown("Detailed EPC view: Tracking which delays are consuming critical programmatic buffer.")
    
    proj_sorted = projects_df.sort_values('Schedule Delay (Days)', ascending=True)
    fig_float = go.Figure()
    
    # Green base layer (Thicker bar)
    fig_float.add_trace(go.Bar(
        y=proj_sorted['Project'], x=proj_sorted['Available Float (Days)'],
        name='Available Float (Buffer)', orientation='h', 
        marker=dict(color='#2ca02c'), # Solid Green
        width=0.7 # Thicker to frame the red overlay
    ))
    
    # Red overlay layer (Thinner bar to show consumption clearly)
    fig_float.add_trace(go.Bar(
        y=proj_sorted['Project'], x=proj_sorted['Schedule Delay (Days)'],
        name='Actual Delay (Drift)', orientation='h', 
        marker=dict(color='#d62728'), # Glaring Red
        width=0.4 # Thinner so it sits "inside" or shoots past the green
    ))
    
    fig_float.update_layout(
        barmode='overlay', # Overlays the bars instead of stacking them
        xaxis_title="Days",
        height=450,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_float, use_container_width=True)

st.markdown("---")
st.subheader("Project Execution Table")
st.dataframe(
    projects_df[['Project', 'External Firm(s)', 'Phase', 'On Critical Path', 'Available Float (Days)', 'Schedule Delay (Days)', 'Slip Status', 'First-Pass Yield (%)', 'NCR / SDR Count']], 
    use_container_width=True, hide_index=True
)
