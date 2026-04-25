import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

st.set_page_config(page_title="Last Energy | Vendor Portfolio", layout="wide")

@st.cache_data
def load_data():
    # Load pristine CSV data
    projects = pd.read_csv("Final_Projects_Data.csv")
    vendors = pd.read_csv("Final_Vendors_Data.csv")
    
    projects.columns = projects.columns.str.strip()
    vendors.columns = vendors.columns.str.strip()
    
    if 'External Firm(s)' in projects.columns:
        projects['External Firm(s)'] = projects['External Firm(s)'].astype(str).str.strip()
    if 'Firm' in vendors.columns:
        vendors['Firm'] = vendors['Firm'].astype(str).str.strip()

    # --- BULLETPROOF DATA PARSING ---
    # Strip symbols ($, %, commas) so users can format the CSV cleanly without breaking the math
    numeric_proj_cols = ['Scope Creep / Change Orders ($)', 'Schedule Delay (Days)', 'Available Float (Days)']
    for col in numeric_proj_cols:
        if col in projects.columns:
            if projects[col].dtype == object:
                projects[col] = projects[col].astype(str).str.replace(r'[$,%]', '', regex=True)
            projects[col] = pd.to_numeric(projects[col], errors='coerce').fillna(0)
            
    numeric_vendor_cols = ['Active SOWs', 'Total Spend ($)', 'Avg First-Pass Yield (%)', 'OTD (%)', 'Total Scope Creep ($)']
    for col in numeric_vendor_cols:
        if col in vendors.columns:
            if vendors[col].dtype == object:
                vendors[col] = vendors[col].astype(str).str.replace(r'[$,%]', '', regex=True)
            vendors[col] = pd.to_numeric(vendors[col], errors='coerce').fillna(0)

    # --- PROJECT METRICS ---
    projects['Budget Status'] = projects['Scope Creep / Change Orders ($)'].apply(lambda x: 'Overrun' if x > 0 else 'On Budget')
    
    def evaluate_slip(row):
        if row['Schedule Delay (Days)'] == 0:
            return "On Track"
        elif row['Schedule Delay (Days)'] <= row['Available Float (Days)']:
            return "Slip (Within Float)"
        else:
            return "CRITICAL PATH IMPACT"
    projects['Slip Status'] = projects.apply(evaluate_slip, axis=1)

    def calculate_priority(row):
        if row['Regulatory Milestone'] == 'MISSED' or row['Slip Status'] == 'CRITICAL PATH IMPACT':
            return 'HIGH (Immediate)'
        elif row['Slip Status'] == 'Slip (Within Float)' or row['Scope Creep / Change Orders ($)'] > 0:
            return 'MEDIUM (Review)'
        else:
            return 'LOW (Monitor)'
    projects['Oversight Priority'] = projects.apply(calculate_priority, axis=1)

    # --- VENDOR METRICS ---
    vendors['Firm_Stacked'] = vendors['Firm'].astype(str).str.replace(' ', '<br>')

    def assign_tier(row):
        if row['Active SOWs'] >= 3 or row['Total Spend ($)'] > 500000:
            return "Tier 1 (Strategic Partner)"
        elif row['Active SOWs'] == 2:
            return "Tier 2 (Preferred)"
        else:
            return "Tier 3 (Transactional)"
    vendors['Vendor Tier'] = vendors.apply(assign_tier, axis=1)

    # Threshold Breaches
    vendors['Threshold Breaches'] = 0
    vendors.loc[vendors['Avg First-Pass Yield (%)'] < 80, 'Threshold Breaches'] += 1 
    vendors.loc[vendors['Total Scope Creep ($)'] > 0, 'Threshold Breaches'] += 1 
    vendors.loc[vendors['OTD (%)'] < 90, 'Threshold Breaches'] += 1 
    
    reg_misses = projects[projects['Regulatory Milestone'] == 'MISSED']['External Firm(s)'].unique()
    vendors.loc[vendors['Firm'].isin(reg_misses), 'Threshold Breaches'] += 2 
    
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

    return projects, vendors

def load_markdown():
    if os.path.exists("assignment_text.md"):
        with open("assignment_text.md", "r") as f:
            return f.read()
    return "Markdown file 'assignment_text.md' not found."

projects_df, vendors_df = load_data()
md_content = load_markdown()

st.title("Last Energy | External Engineering Portfolio")
st.markdown("Dual-pane command center separating day-to-day tactical triage from strategic vendor relationship management.")

# Switch Tab Order and Add 3rd Tab
tab_vendors, tab_projects, tab_prose = st.tabs([
    "Part 1: Strategic Vendor Scorecard (Formal)", 
    "Part 2: Project Operations (Tactical)", 
    "Part 3: Executive Summary"
])

# ==========================================
# TAB 1: VENDOR SCORECARD (Strategic)
# ==========================================
with tab_vendors:
    st.markdown("### Strategic Relationship & Annual Framework")
    st.markdown("**Philosophy:** Formal review cadences shouldn't be blanketed. We segment vendors into Tiers based on our dependency on them (Strategic vs. Transactional). The baseline cadence is set by the Tier, and the *agenda* of those meetings is dictated by threshold breaches across the three pillars: Quality, Engineering, and Commercial.")
    
    st.subheader("Formal Review Matrix & The 3 Pillars")
    
    st.info("""
    **The 3-Pillar Formal Review Agenda:**
    * **Engineering/Technical:** Are they adhering to the schedule? (Target: OTD > 90%)
    * **Quality/Regulatory:** Is the work right the first time? (Target: FPY > 80% & No Reg Misses)
    * **Commercial:** Are they sticking to the baseline budget? (Target: $0 Scope Creep / Change Orders)
    """)
    
    scorecard_df = vendors_df[['Firm', 'Vendor Tier', 'Formal Cadence Strategy', 'Threshold Breaches', 'Avg First-Pass Yield (%)', 'OTD (%)', 'Total Scope Creep ($)']].copy()
    
    scorecard_df = scorecard_df.rename(columns={
        'Avg First-Pass Yield (%)': 'Pillar 1: Quality (FPY)',
        'OTD (%)': 'Pillar 2: Schedule (OTD %)',
        'Total Scope Creep ($)': 'Pillar 3: Commercial Creep'
    })
    
    scorecard_df['Pillar 1: Quality (FPY)'] = scorecard_df['Pillar 1: Quality (FPY)'].apply(lambda x: f"{x:.1f}%")
    scorecard_df['Pillar 2: Schedule (OTD %)'] = scorecard_df['Pillar 2: Schedule (OTD %)'].apply(lambda x: f"{x:.1f}%")
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
        
        clean_vendors = vendors_df.copy()
        clean_vendors = clean_vendors.dropna(subset=["OTD (%)", "Avg First-Pass Yield (%)", "Vendor Tier"])
        
        # Guard clause to prevent Plotly KeyError if dataframe is empty
        if clean_vendors.empty:
            st.warning("Not enough valid numerical data to plot the matrix. Check for empty rows or invalid formatting in your CSV files.")
        else:
            # Ensure Bubble Size is strictly positive so Plotly rendering doesn't crash
            clean_vendors['Total Spend ($)'] = clean_vendors['Total Spend ($)'].replace(0, 10000)

            fig_scatter = px.scatter(
                clean_vendors, x="OTD (%)", y="Avg First-Pass Yield (%)", 
                size="Total Spend ($)", hover_name="Firm", text="Firm_Stacked",
                color="Vendor Tier", color_discrete_sequence=px.colors.qualitative.Set1
            )
            fig_scatter.update_traces(textposition='top center', textfont=dict(size=12), cliponaxis=False)
            fig_scatter.add_hline(y=80, line_dash="dot", annotation_text="Quality Target (80%)", annotation_position="bottom right")
            fig_scatter.add_vline(x=90, line_dash="dot", annotation_text="OTD Target (90%)", annotation_position="top left")
            
            x_min = clean_vendors["OTD (%)"].min()
            y_min = clean_vendors["Avg First-Pass Yield (%)"].min()
            fig_scatter.update_layout(
                xaxis_title="On-Time Delivery (OTD %)", yaxis_title="Avg First-Pass Yield (%)",
                xaxis=dict(range=[max(0, x_min - 10), 105]), yaxis=dict(range=[max(0, y_min - 10), 105]),
                height=350, margin=dict(t=10)
            )
            st.plotly_chart(fig_scatter, use_container_width=True)

    with col2_v:
        st.subheader("Vendor Categorization Breakdown")
        if not vendors_df.empty:
            tier_counts = vendors_df['Vendor Tier'].value_counts().reset_index()
            tier_counts.columns = ['Vendor Tier', 'Count']
            fig_pie = px.pie(tier_counts, values='Count', names='Vendor Tier', hole=0.4, color_discrete_sequence=px.colors.qualitative.Set1)
            fig_pie.update_layout(height=350, margin=dict(t=10, b=10))
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No Vendor Tier data available to display.")

# ==========================================
# TAB 2: PROJECT OPERATIONS & TRIAGE (Tactical)
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
        
        priority_map = {'HIGH (Immediate)': 1, 'MEDIUM (Review)': 2, 'LOW (Monitor)': 3}
        projects_df['Priority_Rank'] = projects_df['Oversight Priority'].map(priority_map)
        priority_df = projects_df.sort_values(['Priority_Rank', 'Days to Next Deliverable'])
        
        display_cols = ['Oversight Priority', 'Project', 'External Firm(s)', 'Regulatory Milestone', 'Budget Status', 'Slip Status']
        
        def color_priority(val):
            val_str = str(val).upper()
            if 'HIGH' in val_str:
                return 'color: #ff4b4b; font-weight: bold;'
            elif 'MEDIUM' in val_str:
                return 'color: #ffa500; font-weight: bold;'
            elif 'LOW' in val_str:
                return 'color: #2ca02c; font-weight: bold;'
            return ''
            
        st.dataframe(
            priority_df[display_cols].style.map(color_priority, subset=['Oversight Priority']), 
            use_container_width=True, hide_index=True, height=300
        )

    with col2_p:
        st.subheader("Schedule Risk (Slip vs. Float)")
        if not projects_df.empty:
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
        else:
            st.info("No Project data available to map Schedule Risk.")

# ==========================================
# TAB 3: PROSE / EXECUTIVE SUMMARY
# ==========================================
with tab_prose:
    st.markdown(md_content)
