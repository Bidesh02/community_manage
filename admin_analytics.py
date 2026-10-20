"""
AegisGate - Interactive Streamlit Executive Analytics Dashboard
Visualizes Society Operations, Maintenance Collections, Gate Peak Hours, and Biometrics.
"""

import os
import sys
import datetime
from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# Configure page layout
st.set_page_config(
    page_title="AegisGate Analytics | Society Intelligence",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling for Obsidian / Slate Glassmorphic Theme
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    .main {
        background-color: #090d16;
        color: #f8fafc;
    }
    .metric-card {
        background: rgba(17, 24, 39, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    }
    .metric-title {
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        color: #94a3b8;
        letter-spacing: 0.05em;
    }
    .metric-value {
        font-size: 2.2rem;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
        margin: 6px 0;
        color: #ffffff;
    }
    .metric-sub {
        font-size: 0.8rem;
        color: #06b6d4;
    }
</style>
""", unsafe_allow_html=True)

# Setup Django Environment to access ORM models
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'society_core.settings')
import django
django.setup()

from society_app.models import User, ComplaintTicket, MaintenanceBill, VisitorLog, BiometricGateLog, SocietyNotice
from django.db.models import Sum, Count, Avg
from django.utils import timezone


# Sidebar Filters
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/shield.png", width=64)
    st.title("AegisGate Admin")
    st.caption("Executive Intelligence Panel v2.4")
    st.divider()

    st.subheader("Filter Controls")
    date_filter = st.selectbox(
        "Time Range",
        ["All Time", "Last 30 Days", "This Quarter", "Year to Date"],
        index=0
    )

    towers = list(User.objects.values_list('block_tower', flat=True).distinct())
    towers = [t for t in towers if t]
    selected_tower = st.selectbox("Filter Tower / Block", ["All Blocks"] + towers)

    st.divider()
    if st.button("🔄 Refresh Data Stream", use_container_width=True):
        st.rerun()

    st.markdown("""
    ---
    **Quick Links**
    - [🌐 Main Society Portal](http://localhost:8000)
    - [👁️ OpenCV Face Gate](http://localhost:8000/gate/terminal/)
    - [⚙️ Django Admin](http://localhost:8000/admin/)
    """)


# Header
st.markdown("""
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid rgba(255,255,255,0.08);">
  <div>
    <h1 style="font-size: 2.1rem; font-weight: 800; margin: 0; background: linear-gradient(90deg, #ffffff, #06b6d4); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
      AegisGate Society Intelligence Dashboard
    </h1>
    <p style="color: #94a3b8; font-size: 0.95rem; margin-top: 4px;">
      Comprehensive analytics across Maintenance collections, Gate Security throughput, and Ticket resolution SLAs.
    </p>
  </div>
  <div style="background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 999px; padding: 6px 16px; color: #34d399; font-weight: 700; font-size: 0.85rem;">
    ● Live Database Link
  </div>
</div>
""", unsafe_allow_html=True)


# Fetch Data
residents_qs = User.objects.filter(role='RESIDENT')
tickets_qs = ComplaintTicket.objects.all()
bills_qs = MaintenanceBill.objects.all()
visitors_qs = VisitorLog.objects.all()
biometrics_qs = BiometricGateLog.objects.all()

total_residents = residents_qs.count()
total_tickets = tickets_qs.count()
resolved_tickets = tickets_qs.filter(status__in=['RESOLVED', 'CLOSED']).count()
open_tickets = tickets_qs.filter(status__in=['OPEN', 'IN_PROGRESS']).count()

total_billed = float(bills_qs.aggregate(t=Sum('amount'))['t'] or 0.0)
total_collected = float(bills_qs.filter(status='PAID').aggregate(t=Sum('amount'))['t'] or 0.0)
collection_rate = (total_collected / total_billed * 100) if total_billed > 0 else 100.0

total_biometric_scans = biometrics_qs.count()
granted_scans = biometrics_qs.filter(access_granted=True).count()
pass_accuracy = (granted_scans / total_biometric_scans * 100) if total_biometric_scans > 0 else 98.4


# Top KPI Metric Cards
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="metric-card">
      <div class="metric-title">Community Residents</div>
      <div class="metric-value">{total_residents}</div>
      <div class="metric-sub">👥 Occupied Apartments</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card">
      <div class="metric-title">Fee Collection Ratio</div>
      <div class="metric-value">{collection_rate:.1f}%</div>
      <div class="metric-sub">💳 ${total_collected:,.2f} Collected</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-card">
      <div class="metric-title">Service Tickets Resolved</div>
      <div class="metric-value">{resolved_tickets}/{total_tickets}</div>
      <div class="metric-sub">⚡ {open_tickets} Active In Queue</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="metric-card">
      <div class="metric-title">Biometric Gate Throughput</div>
      <div class="metric-value">{total_biometric_scans}</div>
      <div class="metric-sub">👁️ OpenCV Facial Matches</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# SECTION 1: Service Request & Complaint Resolution Turnaround Time
st.subheader("🛠️ Maintenance & Issue Resolution SLA Performance")
chart_col1, chart_col2 = st.columns([1.3, 1])

# Tickets by Category
cat_data = tickets_qs.values('category').annotate(count=Count('id'))
cat_df = pd.DataFrame(list(cat_data))
if not cat_df.empty:
    cat_df['category_name'] = cat_df['category'].apply(lambda c: dict(ComplaintTicket.CATEGORY_CHOICES).get(c, c))
    fig_cat = px.bar(
        cat_df,
        x='category_name',
        y='count',
        color='count',
        color_continuous_scale='Viridis',
        labels={'category_name': 'Issue Category', 'count': 'Total Complaints'},
        title="Complaints by Category"
    )
    fig_cat.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(17, 24, 39, 0.7)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=40, b=20)
    )
    chart_col1.plotly_chart(fig_cat, use_container_width=True)
else:
    chart_col1.info("No complaint tickets logged yet.")

# Tickets Status Distribution Donut Chart
status_data = tickets_qs.values('status').annotate(count=Count('id'))
status_df = pd.DataFrame(list(status_data))
if not status_df.empty:
    status_df['status_label'] = status_df['status'].apply(lambda s: dict(ComplaintTicket.STATUS_CHOICES).get(s, s))
    fig_status = px.pie(
        status_df,
        names='status_label',
        values='count',
        hole=0.6,
        color_discrete_sequence=['#f59e0b', '#06b6d4', '#10b981', '#64748b'],
        title="Ticket Resolution Pipeline"
    )
    fig_status.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(17, 24, 39, 0.7)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=40, b=20)
    )
    chart_col2.plotly_chart(fig_status, use_container_width=True)
else:
    chart_col2.info("No status data available.")

st.markdown("<br>", unsafe_allow_html=True)


# SECTION 2: Maintenance Revenue Collections & Dues Breakdown
st.subheader("💰 Financial Ledger & Fee Collection Stream")
fin_col1, fin_col2 = st.columns([1.5, 1])

# Monthly Billed vs Paid
bills_list = list(bills_qs.values('month', 'status', 'amount'))
if bills_list:
    bills_df = pd.DataFrame(bills_list)
    bills_df['amount'] = bills_df['amount'].astype(float)
    monthly_agg = bills_df.groupby(['month', 'status'])['amount'].sum().reset_index()

    fig_fin = px.bar(
        monthly_agg,
        x='month',
        y='amount',
        color='status',
        barmode='group',
        color_discrete_map={'PAID': '#10b981', 'PENDING': '#f59e0b', 'OVERDUE': '#f43f5e'},
        title="Monthly Maintenance Billing & Inflow ($)"
    )
    fig_fin.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(17, 24, 39, 0.7)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=40, b=20)
    )
    fin_col1.plotly_chart(fig_fin, use_container_width=True)
else:
    fin_col1.info("No maintenance bills generated yet.")

# Payment Methods Distribution
paid_bills = bills_df[bills_df['status'] == 'PAID'] if bills_list else pd.DataFrame()
if not paid_bills.empty and 'payment_method' in paid_bills.columns:
    method_counts = paid_bills['payment_method'].value_counts().reset_index()
    method_counts.columns = ['Method', 'Count']
    fig_methods = px.pie(
        method_counts,
        names='Method',
        values='Count',
        title="Payment Channels",
        color_discrete_sequence=['#6366f1', '#06b6d4', '#10b981', '#f59e0b']
    )
    fig_methods.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(17, 24, 39, 0.7)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=40, b=20)
    )
    fin_col2.plotly_chart(fig_methods, use_container_width=True)
else:
    fin_col2.info("Awaiting payment records.")

st.markdown("<br>", unsafe_allow_html=True)


# SECTION 3: Peak Visitor Hours & Gate Traffic Analysis
st.subheader("🚗 Gate Security & Peak Visitor Traffic Patterns")
gate_col1, gate_col2 = st.columns([1.5, 1])

# Generate hourly entry pattern
visitors_list = list(visitors_qs.values('entry_time', 'purpose', 'entry_type'))
if visitors_list:
    vis_df = pd.DataFrame(visitors_list)
    vis_df['hour'] = pd.to_datetime(vis_df['entry_time']).dt.hour
    hourly_counts = vis_df.groupby('hour').size().reindex(range(24), fill_value=0).reset_index()
    hourly_counts.columns = ['Hour of Day (0-23h)', 'Visitor Entries']

    fig_traffic = px.area(
        hourly_counts,
        x='Hour of Day (0-23h)',
        y='Visitor Entries',
        title="Campus Inbound Traffic by Hour of Day",
        color_discrete_sequence=['#06b6d4']
    )
    fig_traffic.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(17, 24, 39, 0.7)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=40, b=20)
    )
    gate_col1.plotly_chart(fig_traffic, use_container_width=True)

    # Visitor Purpose Breakdown
    purpose_df = vis_df['purpose'].value_counts().reset_index()
    purpose_df.columns = ['Purpose', 'Count']
    fig_purpose = px.bar(
        purpose_df.head(6),
        x='Count',
        y='Purpose',
        orientation='h',
        color='Count',
        color_continuous_scale='Purples',
        title="Visitor Purpose Breakdown"
    )
    fig_purpose.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(17, 24, 39, 0.7)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=40, b=20)
    )
    gate_col2.plotly_chart(fig_purpose, use_container_width=True)
else:
    gate_col1.info("No visitor logs recorded yet.")
    gate_col2.info("No visitor breakdown data.")


# SECTION 4: OpenCV Biometric Face Recognition Confidence Metrics
st.subheader("👁️ OpenCV Facial Recognition Accuracy & Confidence")
bio_col1, bio_col2 = st.columns([1, 1])

bio_list = list(biometrics_qs.values('confidence_score', 'matched_role', 'access_granted'))
if bio_list:
    bio_df = pd.DataFrame(bio_list)
    fig_hist = px.histogram(
        bio_df,
        x='confidence_score',
        nbins=15,
        color='access_granted',
        title="OpenCV LBPH Confidence Distribution (%)",
        labels={'confidence_score': 'Confidence Score (%)'},
        color_discrete_map={True: '#10b981', False: '#f43f5e'}
    )
    fig_hist.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(17, 24, 39, 0.7)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=40, b=20)
    )
    bio_col1.plotly_chart(fig_hist, use_container_width=True)

    # Verification Rate Gauge
    avg_conf = bio_df['confidence_score'].mean()
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=avg_conf,
        title={'text': "Average Recognition Match Score"},
        gauge={
            'axis': {'range': [0, 100]},
            'bar': {'color': "#06b6d4"},
            'steps': [
                {'range': [0, 50], 'color': "rgba(244, 63, 94, 0.3)"},
                {'range': [50, 75], 'color': "rgba(245, 158, 11, 0.3)"},
                {'range': [75, 100], 'color': "rgba(16, 185, 129, 0.3)"}
            ]
        }
    ))
    fig_gauge.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(17, 24, 39, 0.7)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=40, b=20)
    )
    bio_col2.plotly_chart(fig_gauge, use_container_width=True)
else:
    bio_col1.info("No biometric entries recorded yet.")
    bio_col2.info("Awaiting gate scans.")

st.markdown("<br><hr style='border-color: rgba(255,255,255,0.08);'>", unsafe_allow_html=True)
st.caption("AegisGate Autonomous Resident & Society Operations Platform • Powered by Django, OpenCV & Streamlit")
