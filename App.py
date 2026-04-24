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
            # Real-world logic: Target is $0. Positive values indicate overbilling/creep.
            'Scope Creep / Change Orders ($)': [0, 120000, 0, 85000, 0], # 2 Projects with Overruns
            'First-Pass Yield (%)': [95, 82, 88, 65, 85],
            'NCR / SDR Count': [0, 2, 0, 5, 1],
            'Regulatory Milestone': ['N/A', 'N/A', 'N/A', 'MISSED', 'N/A'] # 1 Missed Milestone
        })

    # --- DATA CLEANSING ---
    if 'External Firm(s)' in projects.columns:
        projects['External Firm(s)'] = projects['External Firm(s)'].astype(str).str.strip()
    if 'Firm' in vendors.columns:
        vendors['Firm'] = vendors['Firm'].astype(str).str.strip()

    # --- RESILIENCY: AUTO-GENERATE MISSING COLUMNS ---
    np.random.seed(42)
    if 'Regulatory Milestone' not in projects.columns:
        projects['Regulatory Milestone'] = 'N/A'
    if 'Scope Creep / Change Orders ($)' not in projects.columns:
        # Heavily weight towards $0, but introduce some positive creep amounts
        projects['Scope Creep / Change Orders ($)'] = np.random.choice([0, 0, 0, 15000, 45000, 120000], size=len(projects))
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
    
    # Calculate Project-level metrics first: Any amount over $0 is an overrun
    projects['Budget Status'] = projects['Scope Creep / Change Orders ($)'].apply(lambda x: 'Overrun' if x > 0 else 'On Budget')
    
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
        'Scope Creep / Change Orders ($)': 'sum',
        'NCR / SDR Count': 'sum'
    }).reset_index()
    vendors = pd.merge(vendors, vendor_metrics, left_on='Firm', right_on='External Firm(s)', how='left')
    
    vendors['Schedule Delay (Days)'] = vendors['Schedule Delay (Days)'].fillna(0)
    vendors['First-Pass Yield (%)'] = vendors['First-Pass Yield (%)'].fillna(0)
    vendors['Scope Creep / Change Orders ($)'] = vendors['Scope Creep / Change Orders ($)'].fillna(0)
    vendors['NCR / SDR Count'] = vendors['NCR / SDR Count'].fillna(0)
    
    # Extra visual/sizing metrics
    vendors['Firm_Stacked'] = vendors['Firm'].astype(str).str.replace(' ', '<br>')
    sows = projects.groupby('External Firm(s)').size().reset_index(name='Active SOWs')
    if 'Active SOWs' not in vendors.columns:
        vendors = pd.merge(vendors, sows, left_on='Firm', right_on='External Firm(s)', how='left')
        vendors['Active SOWs'] = vendors['Active SOWs'].fillna(1)
        
    # Mock Total Spend for tiering if not present
    if 'Total Spend ($)' not in vendors.columns:
        vendors['Total Spend ($)'] = vendors['Active SOWs'] * np.random.randint(50000, 300000, size=len(vendors))

    # --- FIRST PRINCIPLES: VENDOR TIERING & FORMAL REVIEW CADENCE ---
    # Segment vendors by volume/dependency to dictate the *Formal* review cycle
    def assign_tier(row):
        if row['Active SOWs'] >= 3 or row['Total Spend ($)'] > 500000:
            return "Tier 1 (Strategic Partner)"
        elif row['Active SOWs'] == 2:
            return "Tier 2 (Preferred)"
        else:
            return "Tier 3 (Transactional)"
    vendors['Vendor Tier'] = vendors.apply(assign_tier, axis=1)

    # Threshold Breaches dictate the AGENDA and URGENCY of the review
    vendors['Threshold Breaches'] = 0
    vendors.loc[vendors['First-Pass Yield (%)'] < 80, 'Threshold Breaches'] += 1 # Quality Breach
    vendors.loc[vendors['Scope Creep / Change Orders ($)'] > 0, 'Threshold Breaches'] += 1 # Commercial Breach (Any $>0)
    vendors.loc[vendors['Schedule Delay (Days)'] > 10, 'Threshold Breaches'] += 1 # Schedule/Eng Breach
    
    reg_misses = projects[projects['Regulatory Milestone'] == 'MISSED']['External Firm(s)'].unique()
    vendors.loc[vendors['Firm'].isin(reg_misses), 'Threshold Breaches'] += 2 # Heavy penalty
    
    # Matrix: Tier + Health = Formal Review Action
    def assign_formal_cadence(row):
        tier = row['Vendor Tier']
        breaches = row['Threshold Breaches']
        
        if "Tier 1" in tier:
            if breaches == 0: return "Bi-Annual Formal Review"
            else: return "Quarterly Formal + Active CAP"
        elif "Tier 2" in tier:
            if breaches == 0: return "Annual Formal Review"
            else: return "Bi-Annual Formal + CAP"
        else:
            if breaches == 0: return "As-Needed (Post-Project)"
            else: return "Hold on Future POs"
            
    vendors['Formal Cadence Strategy'] = vendors.apply(assign_formal_cadence, axis=1)
        
    projects['Days to Next Deliverable'] = np.random.randint(2, 35, size=len(projects))
    
    # Tactical priority remains for Tab 1 (Day-to-day operations)
    def calculate_priority(row):
        if row['Regulatory Milestone'] == 'MISSED' or row['Slip Status'] == 'CRITICAL PATH IMPACT':
            return '🔴 HIGH (Immediate)'
        elif row['Slip Status'] == 'Slip (Within Float)' or row['Scope Creep / Change Orders ($)'] > 0:
            return '🟡 MEDIUM (Review)'
        else:
            return '🟢 LOW (Monitor)'
    projects['Oversight Priority'] = projects.apply(calculate_priority, axis=1)
    
    return projects, vendors

projects_df, vendors_df = load_data()

st.title("Last Energy | External Engineering Portfolio")
st.markdown("Dual-pane command center separating day-to-day tactical triage from strategic vendor relationship management.")

tab_projects, tab_vendors = st.tabs(["🏗️ Part 2: Project Operations (Tactical)", "🏢 Part 1: Strategic Vendor Scorecard (Formal)"])

# ==========================================
# TAB 1: PROJECT OPERATIONS & TRIAGE (PART 2)
# ==========================================
with tab_projects:
    st.markdown("### Portfolio Execution & Day-to-Day Intervention")
    st.markdown("This view is for the Engineering Leads. It tracks immediate deliverables, schedule slips, and active interventions.")
    
    pc1, pc2, pc3, pc4 = st.columns(4)
    budget_overruns = len(projects_df[projects_df['Scope Creep / Change Orders ($)'] > 0])
    missed_reg = len(projects_df[projects_df['Regulatory Milestone'] == 'MISSED'])
    critical_slips = len(projects_df[projects_df['Slip Status'] == 'CRITICAL PATH IMPACT'])
    
    pc1.metric("Active Concurrent Projects", len(projects_df))
    pc2.metric("Active SOW Overruns", budget_overruns, delta="Flagged" if budget_overruns > 0 else "Clear", delta_color="inverse")
    pc3.metric("Missed Reg. Milestones", missed_reg, delta="Critical Risk" if missed_reg > 0 else "Clear", delta_color="inverse")
    pc4.metric("Critical Path Breaches", critical_slips, delta="Schedule Risk" if critical_slips > 0 else "Clear", delta_color="inverse")

    st.markdown("---")

    col1_p, col2_p = st.columns([1.2, 1])

    with col1_p:
        st.subheader("Actionable Triage Queue")
        
        priority_map = {'🔴 HIGH (Immediate)': 1, '🟡 MEDIUM (Review)': 2, '🟢 LOW (Monitor)': 3}
        projects_df['Priority_Rank'] = projects_df['Oversight Priority'].map(priority_map)
        priority_df = projects_df.sort_values(['Priority_Rank', 'Days to Next Deliverable'])
        
        st.dataframe(
            priority_df[['Oversight Priority', 'Project', 'External Firm(s)', 'Regulatory Milestone', 'Budget Status', 'Slip Status']], 
            use_container_width=True, hide_index=True, height=300
        )

    with col2_p:
        st.subheader("Schedule Risk (Slip vs. Float)")
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
    st.markdown("### Strategic Relationship & Annual Framework")
    st.markdown("**Philosophy:** Formal review cadences shouldn't be blanketed. We segment vendors into Tiers based on our dependency on them (Strategic vs. Transactional). The baseline cadence is set by the Tier, and the *agenda* of those meetings is dictated by threshold breaches across the three pillars: Quality, Engineering, and Commercial.")
    
    st.subheader("Formal Review Matrix & The 3 Pillars")
    
    # Define the 3 pillars clearly
    st.info("""
    **The 3-Pillar Formal Review Agenda:**
    * 🏗️ **Engineering/Technical:** Are they adhering to the schedule? (Flag: >10d Avg Drift)
    * 🔬 **Quality/Regulatory:** Is the work right the first time? (Flag: FPY < 80% or Reg Misses)
    * 💰 **Commercial:** Are they sticking to the baseline budget? (Target: $0. Flag: Any Scope Creep / Change Orders)
    """)
    
    # Format the scorecard to clearly show the 3 pillars
    scorecard_df = vendors_df[['Firm', 'Vendor Tier', 'Formal Cadence Strategy', 'Threshold Breaches', 'First-Pass Yield (%)', 'Schedule Delay (Days)', 'Scope Creep / Change Orders ($)']].copy()
    
    # Rename columns to reflect the pillars for the UI
    scorecard_df = scorecard_df.rename(columns={
        'First-Pass Yield (%)': 'Pillar 1: Quality (FPY)',
        'Schedule Delay (Days)': 'Pillar 2: Eng/Schedule Drift',
        'Scope Creep / Change Orders ($)': 'Pillar 3: Commercial Creep'
    })
    
    scorecard_df['Pillar 1: Quality (FPY)'] = scorecard_df['Pillar 1: Quality (FPY)'].apply(lambda x: f"{x:.1f}%")
    scorecard_df['Pillar 2: Eng/Schedule Drift'] = scorecard_df['Pillar 2: Eng/Schedule Drift'].apply(lambda x: f"{x:.1f} days")
    scorecard_df['Pillar 3: Commercial Creep'] = scorecard_df['Pillar 3: Commercial Creep'].apply(lambda x: f"${x:,.0f}")
    
    scorecard_df = scorecard_df.sort_values(['Vendor Tier', 'Threshold Breaches'], ascending=[True, False])
    
    def highlight_breaches(val):
        color = '#ff4b4b' if isinstance(val, (int, float)) and val > 0 else ''
        return f'background-color: {color}'
        
    st.dataframe(
        scorecard_df.style.map(highlight_breaches, subset=['Threshold Breaches']),
        use_container_width=True, hide_index=True
    )

    st.markdown("---")

    col1_v, col2_v = st.columns(2)

    with col1_v:
        st.subheader("Vendor Risk Matrix (Quality vs. Delivery)")
        fig_scatter = px.scatter(
            vendors_df, x="Schedule Delay (Days)", y="First-Pass Yield (%)", 
            size="Total Spend ($)", hover_name="Firm", text="Firm_Stacked",
            color="Vendor Tier", color_discrete_sequence=px.colors.qualitative.Set1
        )
        fig_scatter.update_traces(textposition='top center', textfont=dict(size=12), cliponaxis=False)
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
        st.subheader("Vendor Categorization Breakdown")
        tier_counts = vendors_df['Vendor Tier'].value_counts().reset_index()
        tier_counts.columns = ['Vendor Tier', 'Count']
        fig_pie = px.pie(tier_counts, values='Count', names='Vendor Tier', hole=0.4, color_discrete_sequence=px.colors.qualitative.Set1)
        fig_pie.update_layout(height=350, margin=dict(t=10, b=10))
        st.plotly_chart(fig_pie, use_container_width=True)
