import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Last Energy | Vendor Portfolio", layout="wide")

@st.cache_data
def load_data():
    # Attempt to load CSVs, fallback to perfectly constrained mock data if not found or empty
    try:
        projects = pd.read_csv("Final_Projects_Data.csv")
        vendors = pd.read_csv("Final_Vendors_Data.csv")
        projects.columns = projects.columns.str.strip()
        vendors.columns = vendors.columns.str.strip()
    except (FileNotFoundError, pd.errors.EmptyDataError):
        # MOCK DATA MATCHING EXACT PROMPT CONSTRAINTS (4 Vendors, 5 Projects)
        vendors = pd.DataFrame({
            'Firm': ['Apex Civil Works', 'Quantum Mechanical', 'Volt Power Systems', 'ReguCore Consulting'],
            'Discipline': ['Civil', 'Mechanical', 'Electrical', 'Regulatory']
        })
        projects = pd.DataFrame({
            'Project': ['Site Prep - TX', 'Reactor Cooling Loop', 'Substation Integration', 'NRC License App', 'Containment Vessel Design'],
            'External Firm(s)': ['Apex Civil Works', 'Quantum Mechanical', 'Volt Power Systems', 'ReguCore Consulting', 'Quantum Mechanical'],
            'Phase': ['Construction', 'Prototyping', 'Design', 'Regulatory', 'Design'],
            'Available Float (Days)': [10, 25, 5, 0, 30],
            'Schedule Delay (Days)': [0, 5, 18, 45, 2], # ReguCore severely delayed
            'Cost Variance (CV)': [5000, -120000, 2000, -85000, 10000], # 2 Projects with Overruns (-)
            'First-Pass Yield (%)': [95, 82, 88, 65, 85],
            'NCR / SDR Count': [0, 2, 0, 5, 1],
            'Regulatory Milestone': ['N/A', 'N/A', 'N/A', 'MISSED', 'N/A'] # 1 Missed Milestone
        })

    # --- RESILIENCY: AUTO-GENERATE MISSING COLUMNS ---
    # Ensures the app doesn't crash if your custom CSV is missing the newly added nuclear columns
    np.random.seed(42)
    
    if 'Regulatory Milestone' not in projects.columns:
        projects['Regulatory Milestone'] = 'N/A'
    if 'Cost Variance (CV)' not in projects.columns:
        projects['Cost Variance (CV)'] = np.random.randint(-50000, 20000, size=len(projects))
    if 'Schedule Delay (Days)' not in projects.columns:
        projects['Schedule Delay (Days)'] = np.random.randint(0, 25, size=len(projects))
    if 'Available Float (Days)' not in projects.columns:
        projects['Available Float (Days)'] = np.random.randint(5, 30, size=len(projects))
    if 'First-Pass Yield (%)' not in projects.columns:
        projects['First-Pass Yield (%)'] = np.random.uniform(70, 99, size=len(projects))
    if 'NCR / SDR Count' not in projects.columns:
        projects['NCR / SDR Count'] = np.random.randint(0, 4, size=len(projects))
    if 'Discipline' not in vendors.columns:
        vendors['Discipline'] = 'General Engineering'

    # --- PART 1: NUCLEAR VENDOR SCORING FRAMEWORK ---
    
    # Calculate Project-level metrics first
    projects['Budget Status'] = projects['Cost Variance (CV)'].apply(lambda x: 'Overrun' if x < 0 else 'On Budget')
    
    # Identify slip severity
    def evaluate_slip(row):
        if row['Schedule Delay (Days)'] == 0:
            return "On Track"
        elif row['Schedule Delay (Days)'] <= row['Available Float (Days)']:
            return "Slip (Within Float)"
        else:
            return "CRITICAL PATH IMPACT"
    projects['Slip Status'] = projects.apply(evaluate_slip, axis=1)

    # Rollup vendor metrics for the Scorecard
    vendor_metrics = projects.groupby('External Firm(s)').agg({
        'Schedule Delay (Days)': 'mean',
        'First-Pass Yield (%)': 'mean',
        'Cost Variance (CV)': 'sum',
        'NCR / SDR Count': 'sum'
    }).reset_index()
    vendors = pd.merge(vendors, vendor_metrics, left_on='Firm', right_on='External Firm(s)', how='left')
    
    # --- FIRST PRINCIPLES: THRESHOLD-BASED TRIAGE (No Arbitrary Scores) ---
    # Instead of arbitrary weights, we count objective threshold breaches.
    vendors['Threshold Breaches'] = 0
    vendors.loc[vendors['First-Pass Yield (%)'] < 80, 'Threshold Breaches'] += 1 # Quality Breach
    vendors.loc[vendors['Cost Variance (CV)'] < 0, 'Threshold Breaches'] += 1    # Commercial Breach
    vendors.loc[vendors['Schedule Delay (Days)'] > 10, 'Threshold Breaches'] += 1 # Schedule Breach
    
    # Check for critical missed regulatory milestones
    reg_misses = projects[projects['Regulatory Milestone'] == 'MISSED']['External Firm(s)'].unique()
    vendors.loc[vendors['Firm'].isin(reg_misses), 'Threshold Breaches'] += 2 # Heavy penalty for Reg misses
    
    # Determine Review Cadence based on objective flags
    def assign_cadence(breaches):
        if breaches == 0: return "Monthly (Commercial Scorecard)"
        elif breaches == 1: return "Bi-Weekly (Engineering Tag-up)"
        else: return "Weekly (Exec Escalation / CAP)"
    vendors['Recommended Cadence'] = vendors['Threshold Breaches'].apply(assign_cadence)

    # --- RESILIENCY: EXTRA VISUAL METRICS ---
    vendors['Firm_Stacked'] = vendors['Firm'].astype(str).str.replace(' ', '<br>')
    sows = projects.groupby('External Firm(s)').size().reset_index(name='Active SOWs')
    if 'Active SOWs' not in vendors.columns:
        vendors = pd.merge(vendors, sows, left_on='Firm', right_on='External Firm(s)', how='left')
        vendors['Active SOWs'] = vendors['Active SOWs'].fillna(1)
        
    projects['Days to Next Deliverable'] = np.random.randint(2, 35, size=len(projects))
    
    def calculate_priority(row):
        if row['Regulatory Milestone'] == 'MISSED' or row['Slip Status'] == 'CRITICAL PATH IMPACT':
            return '🔴 HIGH (Immediate)'
        elif row['Slip Status'] == 'Slip (Within Float)' or row['Cost Variance (CV)'] < 0:
            return '🟡 MEDIUM (Review)'
        else:
            return '🟢 LOW (Monitor)'
    projects['Oversight Priority'] = projects.apply(calculate_priority, axis=1)
    
    return projects, vendors

projects_df, vendors_df = load_data()

st.title("Last Energy | External Engineering Portfolio")
st.markdown("Dual-pane command center mapping programmatic execution and vendor performance frameworks.")

tab_projects, tab_vendors = st.tabs(["🏗️ Part 2: Project Operations & Triage", "🏢 Part 1: Vendor Scorecard & Framework"])

# ==========================================
# TAB 1: PROJECT OPERATIONS & TRIAGE (PART 2)
# ==========================================
with tab_projects:
    st.markdown("### Portfolio Execution & Critical Path Management")
    
    # Specific Callouts for the Prompt's constraints
    pc1, pc2, pc3, pc4 = st.columns(4)
    budget_overruns = len(projects_df[projects_df['Cost Variance (CV)'] < 0])
    missed_reg = len(projects_df[projects_df['Regulatory Milestone'] == 'MISSED'])
    critical_slips = len(projects_df[projects_df['Slip Status'] == 'CRITICAL PATH IMPACT'])
    
    pc1.metric("Active Concurrent Projects", len(projects_df))
    pc2.metric("Active Budget Overruns", budget_overruns, delta="Flagged" if budget_overruns > 0 else "Clear", delta_color="inverse")
    pc3.metric("Missed Reg. Milestones", missed_reg, delta="Critical Risk" if missed_reg > 0 else "Clear", delta_color="inverse")
    pc4.metric("Critical Path Breaches", critical_slips, delta="Schedule Risk" if critical_slips > 0 else "Clear", delta_color="inverse")

    st.markdown("---")

    col1_p, col2_p = st.columns([1.2, 1])

    with col1_p:
        st.subheader("Actionable Triage Queue")
        st.markdown("Prioritized by missed regulatory gates, active budget overruns, and schedule breaches.")
        
        priority_map = {'🔴 HIGH (Immediate)': 1, '🟡 MEDIUM (Review)': 2, '🟢 LOW (Monitor)': 3}
        projects_df['Priority_Rank'] = projects_df['Oversight Priority'].map(priority_map)
        priority_df = projects_df.sort_values(['Priority_Rank', 'Days to Next Deliverable'])
        
        st.dataframe(
            priority_df[['Oversight Priority', 'Project', 'External Firm(s)', 'Regulatory Milestone', 'Budget Status', 'Slip Status']], 
            use_container_width=True, hide_index=True, height=300
        )

    with col2_p:
        st.subheader("Schedule Risk (Slip vs. Float)")
        st.markdown("Tracking which delays are consuming programmatic buffer.")
        proj_sorted = projects_df.sort_values('Schedule Delay (Days)', ascending=True)
        fig_float = go.Figure()
        fig_float.add_trace(go.Bar(
            y=proj_sorted['Project'], x=proj_sorted['Available Float (Days)'],
            name='Available Float (Buffer)', orientation='h', marker=dict(color='#2ca02c'), width=0.7 
        ))
        fig_float.add_trace(go.Bar(
            y=proj_sorted['Project'], x=proj_sorted['Schedule Delay (Days)'],
            name='Actual Delay (Drift)', orientation='h', marker=dict(color='#d62728'), width=0.4 
        ))
        fig_float.update_layout(barmode='overlay', xaxis_title="Days", height=300, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig_float, use_container_width=True)

# ==========================================
# TAB 2: VENDOR SCORECARD (PART 1)
# ==========================================
with tab_vendors:
    st.markdown("### First Principles: Threshold-Based Vendor Health")
    st.markdown("**Philosophy:** Arbitrary weighted scores (e.g., 40% Quality / 30% Cost) break down across different engineering disciplines and contract types. This dashboard prioritizes raw data transparency. Vendors are managed by exception: baseline thresholds are set, and breaches trigger automated review cadences.")
    
    st.subheader("Objective Health Baseline & Actionable Cadence")
    
    # Define what "Review" actually means for the panel
    st.info("""
    **Defining the "Review" Cadence:**
    * 🟢 **Monthly (Commercial Scorecard):** 0 Breaches. Vendor is executing autonomously. Meeting owned by Procurement/Commercial to review invoices and baseline SOW compliance. Engineering is largely exempt.
    * 🟡 **Bi-Weekly (Engineering Tag-up):** 1 Breach. Tactical schedule or quality slip. Meeting owned by the internal Technical/Engineering Lead to unblock constraints and review upcoming deliverables.
    * 🔴 **Weekly (Exec Escalation / CAP):** 2+ Breaches. Critical failure (e.g., missed Reg Milestone). Meeting owned by Dir. External Engineering. Triggers formal Corrective Action Plan (CAP) and potential on-site quality audit.
    """)
    
    # Format the scorecard for presentation
    scorecard_df = vendors_df[['Firm', 'Discipline', 'Recommended Cadence', 'Threshold Breaches', 'First-Pass Yield (%)', 'Schedule Delay (Days)', 'Cost Variance (CV)', 'NCR / SDR Count']].copy()
    
    scorecard_df['First-Pass Yield (%)'] = scorecard_df['First-Pass Yield (%)'].apply(lambda x: f"{x:.1f}%")
    scorecard_df['Schedule Delay (Days)'] = scorecard_df['Schedule Delay (Days)'].apply(lambda x: f"{x:.1f} days")
    scorecard_df['Cost Variance (CV)'] = scorecard_df['Cost Variance (CV)'].apply(lambda x: f"${x:,.0f}")
    
    # Sort by highest breaches to highlight immediate attention
    scorecard_df = scorecard_df.sort_values('Threshold Breaches', ascending=False)
    
    # Use Streamlit's built in styling to highlight breaches
    def highlight_breaches(val):
        color = '#ff4b4b' if isinstance(val, (int, float)) and val > 0 else ''
        return f'background-color: {color}'
        
    st.dataframe(
        scorecard_df.style.applymap(highlight_breaches, subset=['Threshold Breaches']),
        use_container_width=True, hide_index=True
    )

    st.markdown("---")

    col1_v, col2_v = st.columns(2)

    with col1_v:
        st.subheader("Vendor Risk Matrix (Quality vs. Delivery)")
        st.markdown("Visualizing raw execution risk.")
        fig_scatter = px.scatter(
            vendors_df, x="Schedule Delay (Days)", y="First-Pass Yield (%)", 
            size="Active SOWs", hover_name="Firm", text="Firm_Stacked",
            color="First-Pass Yield (%)", color_continuous_scale="RdYlGn"
        )
        fig_scatter.update_traces(textposition='top center', textfont=dict(size=12, color="white"), cliponaxis=False)
        fig_scatter.add_hline(y=80, line_dash="dot", annotation_text="Quality Target (<80% Flags)", annotation_position="bottom right")
        fig_scatter.add_vline(x=10, line_dash="dot", annotation_text="Delay Threshold (>10d Flags)", annotation_position="top right")
        
        x_max = vendors_df["Schedule Delay (Days)"].max() if pd.notna(vendors_df["Schedule Delay (Days)"].max()) else 30
        y_max = vendors_df["First-Pass Yield (%)"].max() if pd.notna(vendors_df["First-Pass Yield (%)"].max()) else 90
        fig_scatter.update_layout(
            xaxis_title="Avg Schedule Delay (Days)", yaxis_title="First-Pass Yield (%)",
            xaxis=dict(range=[-5, max(x_max + 10, 40)]), yaxis=dict(range=[65, max(y_max + 5, 100)]),
            height=350, margin=dict(t=10)
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    with col2_v:
        st.subheader("Commercial & Compliance Wrap-up")
        
        # Displaying the raw data that feeds the commercial/compliance scores
        raw_metrics = vendors_df[['Firm', 'Cost Variance (CV)', 'NCR / SDR Count', 'Active SOWs']].copy()
        raw_metrics['Cost Variance (CV)'] = raw_metrics['Cost Variance (CV)'].apply(lambda x: f"${x:,.0f}")
        
        st.dataframe(raw_metrics, use_container_width=True, hide_index=True)
