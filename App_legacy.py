import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="External Eng Services", layout="wide")

@st.cache_data
def load_data():
    projects = pd.read_csv("Final_Projects_Data.csv")
    vendors = pd.read_csv("Final_Vendors_Data.csv")
    
    projects.columns = projects.columns.str.strip()
    vendors.columns = vendors.columns.str.strip()
    
    # --- RESILIENCY: VENDOR COMMERCIAL METRICS ---
    np.random.seed(42) # Keep mock data consistent across reloads
    if 'Firm_Stacked' not in vendors.columns and 'Firm' in vendors.columns:
        vendors['Firm_Stacked'] = vendors['Firm'].astype(str).str.replace(' ', '<br>')
        
    if 'Active SOWs' not in vendors.columns and 'External Firm(s)' in projects.columns:
        sows = projects.groupby('External Firm(s)').size().reset_index(name='Active SOWs')
        vendors = pd.merge(vendors, sows, left_on='Firm', right_on='External Firm(s)', how='left')
        vendors['Active SOWs'] = vendors['Active SOWs'].fillna(1)

    # Auto-generate Procurement/Commercial metrics if missing
    if 'Initial Contract Value ($)' not in vendors.columns:
        vendors['Initial Contract Value ($)'] = np.random.randint(250000, 1500000, size=len(vendors))
    if 'Scope Creep / Pricing Miss ($)' not in vendors.columns:
        vendors['Scope Creep / Pricing Miss ($)'] = vendors['Initial Contract Value ($)'] * np.random.uniform(0.02, 0.18, size=len(vendors))
    if 'Total Spend ($)' not in vendors.columns:
        vendors['Total Spend ($)'] = vendors['Initial Contract Value ($)'] + vendors['Scope Creep / Pricing Miss ($)']
    if 'SOW Compliance (%)' not in vendors.columns:
        vendors['SOW Compliance (%)'] = np.random.uniform(82, 99, size=len(vendors))
    if 'Total Rework Hours' not in vendors.columns:
        vendors['Total Rework Hours'] = np.random.randint(15, 250, size=len(vendors))

    # --- RESILIENCY: PROJECT METRICS ---
    if 'Days to Next Deliverable' not in projects.columns:
        projects['Days to Next Deliverable'] = np.random.randint(2, 35, size=len(projects))
        
    if 'Days to Project Close' not in projects.columns:
        projects['Days to Project Close'] = projects['Days to Next Deliverable'] + np.random.randint(15, 120, size=len(projects))
        
    if 'Milestone Progress' not in projects.columns:
        current_m = np.random.randint(1, 4, size=len(projects))
        total_m = current_m + np.random.randint(0, 3, size=len(projects))
        projects['Milestone Progress'] = [
            "Final" if c == t else f"{c} of {t}" 
            for c, t in zip(current_m, total_m)
        ]
    
    # Identify slip severity
    def evaluate_slip(row):
        if row['Schedule Delay (Days)'] == 0:
            return "On Track"
        elif row['Schedule Delay (Days)'] <= row['Available Float (Days)']:
            return "Slip (Within Float)"
        else:
            return "CRITICAL PATH IMPACT"
            
    projects['Slip Status'] = projects.apply(evaluate_slip, axis=1)
    
    # Synthesize Oversight Priority
    def calculate_priority(row):
        if row['Slip Status'] == 'CRITICAL PATH IMPACT' or row['Days to Next Deliverable'] <= 7:
            return '🔴 HIGH'
        elif row['Slip Status'] == 'Slip (Within Float)' or row['Days to Next Deliverable'] <= 14:
            return '🟡 MEDIUM'
        else:
            return '🟢 LOW'
            
    projects['Oversight Priority'] = projects.apply(calculate_priority, axis=1)
    
    # Rollup vendor metrics for the Risk Matrix
    vendor_metrics = projects.groupby('External Firm(s)').agg({
        'Schedule Delay (Days)': 'mean',
        'First-Pass Yield (%)': 'mean'
    }).reset_index()
    vendors = pd.merge(vendors, vendor_metrics, left_on='Firm', right_on='External Firm(s)', how='left')
    
    return projects, vendors

projects_df, vendors_df = load_data()

st.title("External Engineering Services Command Center")
st.markdown("Dual-pane view balancing tactical project triage and strategic vendor management.")

# Create the two main views
tab_projects, tab_vendors = st.tabs(["🏗️ Project Operations & Triage", "🏢 Vendor Performance & Commercials"])

# ==========================================
# TAB 1: PROJECT OPERATIONS & TRIAGE
# ==========================================
with tab_projects:
    st.markdown("### Tactical Engineering Intervention")
    
    # Project KPIs
    pc1, pc2, pc3, pc4 = st.columns(4)
    active_projs = len(projects_df)
    critical_slips = len(projects_df[projects_df['Slip Status'] == 'CRITICAL PATH IMPACT'])
    high_priority = len(projects_df[projects_df['Oversight Priority'] == '🔴 HIGH'])
    
    pc1.metric("Active Managed Projects", active_projs)
    pc2.metric("Critical Path Breaches", critical_slips, delta="- High Risk" if critical_slips > 0 else "Clear", delta_color="inverse")
    pc3.metric("Imminent / High Priority Interventions", high_priority)
    pc4.metric("Total Hardware Non-Conformances", projects_df['NCR / SDR Count'].sum())

    st.markdown("---")

    col1_p, col2_p = st.columns([1.2, 1])

    with col1_p:
        st.subheader("Oversight Prioritization Queue")
        st.markdown("Ranked by upcoming deliverables and critical path impact to guide engineering bandwidth.")
        
        priority_map = {'🔴 HIGH': 1, '🟡 MEDIUM': 2, '🟢 LOW': 3}
        projects_df['Priority_Rank'] = projects_df['Oversight Priority'].map(priority_map)
        priority_df = projects_df.sort_values(['Priority_Rank', 'Days to Next Deliverable'])
        
        st.dataframe(
            priority_df[['Oversight Priority', 'Project', 'External Firm(s)', 'Days to Next Deliverable', 'Milestone Progress', 'Slip Status']], 
            use_container_width=True, 
            hide_index=True,
            height=300
        )

    with col2_p:
        st.subheader("Schedule Risk (Slip vs. Float)")
        st.markdown("Tracking which delays are consuming programmatic buffer.")
        
        proj_sorted = projects_df.sort_values('Schedule Delay (Days)', ascending=True)
        fig_float = go.Figure()
        fig_float.add_trace(go.Bar(
            y=proj_sorted['Project'], x=proj_sorted['Available Float (Days)'],
            name='Available Float (Buffer)', orientation='h', 
            marker=dict(color='#2ca02c'), width=0.7 
        ))
        fig_float.add_trace(go.Bar(
            y=proj_sorted['Project'], x=proj_sorted['Schedule Delay (Days)'],
            name='Actual Delay (Drift)', orientation='h', 
            marker=dict(color='#d62728'), width=0.4 
        ))
        fig_float.update_layout(barmode='overlay', xaxis_title="Days", height=300, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig_float, use_container_width=True)

# ==========================================
# TAB 2: VENDOR PERFORMANCE & COMMERCIALS
# ==========================================
with tab_vendors:
    st.markdown("### Strategic Vendor & Procurement Management")
    
    # Vendor KPIs
    vc1, vc2, vc3, vc4 = st.columns(4)
    total_spend = vendors_df['Total Spend ($)'].sum()
    total_creep = vendors_df['Scope Creep / Pricing Miss ($)'].sum()
    avg_fpy = vendors_df['First-Pass Yield (%)'].mean()
    total_rework = vendors_df['Total Rework Hours'].sum()
    
    vc1.metric("Total Active Spend", f"${total_spend:,.0f}")
    vc2.metric("Total Pricing Miss / Scope Creep", f"${total_creep:,.0f}", delta=f"{(total_creep/total_spend)*100:.1f}% of Spend", delta_color="inverse")
    vc3.metric("Portfolio Avg Quality (FPY)", f"{avg_fpy:.1f}%")
    vc4.metric("Total Rework Hours Subsidized", f"{total_rework:,.0f} hrs")

    st.markdown("---")

    col1_v, col2_v = st.columns(2)

    with col1_v:
        st.subheader("Vendor Risk Matrix (Quality vs. Delivery)")
        st.markdown("Assessing technical delivery risk against historical schedule performance.")
        fig_scatter = px.scatter(
            vendors_df, 
            x="Schedule Delay (Days)", 
            y="First-Pass Yield (%)", 
            size="Active SOWs",
            hover_name="Firm",
            text="Firm_Stacked",
            color="First-Pass Yield (%)", 
            color_continuous_scale="RdYlGn"
        )
        fig_scatter.update_traces(textposition='top center', textfont=dict(size=12, color="white"), cliponaxis=False)
        fig_scatter.add_hline(y=80, line_dash="dot", annotation_text="Quality Target", annotation_position="bottom right")
        fig_scatter.add_vline(x=30, line_dash="dot", annotation_text="Delay Threshold", annotation_position="top right")
        
        x_max = vendors_df["Schedule Delay (Days)"].max() if pd.notna(vendors_df["Schedule Delay (Days)"].max()) else 30
        y_max = vendors_df["First-Pass Yield (%)"].max() if pd.notna(vendors_df["First-Pass Yield (%)"].max()) else 90
        fig_scatter.update_layout(
            xaxis_title="Avg Schedule Delay (Days)", yaxis_title="First-Pass Yield (%)",
            xaxis=dict(range=[-5, max(x_max + 10, 40)]), yaxis=dict(range=[65, max(y_max + 5, 100)]),
            height=350, margin=dict(t=10)
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    with col2_v:
        st.subheader("Financial Execution & Scope Creep")
        st.markdown("Comparing initial contracted value vs. downstream pricing misses and creep.")
        fig_spend = go.Figure()
        
        fig_spend.add_trace(go.Bar(
            x=vendors_df['Firm'], y=vendors_df['Initial Contract Value ($)'],
            name='Initial Contract Value', marker_color='#1f77b4'
        ))
        fig_spend.add_trace(go.Bar(
            x=vendors_df['Firm'], y=vendors_df['Scope Creep / Pricing Miss ($)'],
            name='Scope Creep / Pricing Miss', marker_color='#ff7f0e'
        ))
        
        fig_spend.update_layout(
            barmode='stack', yaxis_title="Dollars ($)",
            height=350, margin=dict(t=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_spend, use_container_width=True)

    st.markdown("---")
    st.subheader("Vendor Commercial & Quality Ledger")
    
    # Format currency and percentages for the dataframe display
    display_vendors = vendors_df[['Firm', 'Active SOWs', 'Initial Contract Value ($)', 'Scope Creep / Pricing Miss ($)', 'SOW Compliance (%)', 'Total Rework Hours', 'First-Pass Yield (%)']].copy()
    display_vendors['Initial Contract Value ($)'] = display_vendors['Initial Contract Value ($)'].apply(lambda x: f"${x:,.0f}")
    display_vendors['Scope Creep / Pricing Miss ($)'] = display_vendors['Scope Creep / Pricing Miss ($)'].apply(lambda x: f"${x:,.0f}")
    display_vendors['SOW Compliance (%)'] = display_vendors['SOW Compliance (%)'].apply(lambda x: f"{x:.1f}%")
    display_vendors['First-Pass Yield (%)'] = display_vendors['First-Pass Yield (%)'].apply(lambda x: f"{x:.1f}%")
    
    st.dataframe(display_vendors, use_container_width=True, hide_index=True)
