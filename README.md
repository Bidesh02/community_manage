# 🛡️ AegisGate — Residential Society Operations Platform

An enterprise-grade, luxury residential society management platform engineered with **Django 6**, **Django REST Framework**, **OpenCV Computer Vision (Biometric Face Recognition)**, and an **Interactive Streamlit Executive Analytics Dashboard**.

---

## 🌟 Highlight Features

### 1. 👁️ Standout Feature: Real-Time OpenCV Facial Recognition Gate Scanner
- **Fast-Track Entry**: Powered by OpenCV Haar Cascade Face Detectors & LBPH (Local Binary Patterns Histograms) Face Recognizer.
- **Biometric Calibration**: Automatically trains facial embeddings from enrolled resident & regular staff profile portraits.
- **Futuristic Security HUD**: Live webcam feed with dynamic scanning laser, target crosshair, and real-time bounding box annotations.
- **Autonomous Clearance**: When a match is confirmed (e.g. `John Doe [A-402]`), the gate automatically grants access, chimes, and logs an entry to the audit trail with confidence scoring.
- **Dual Mode**: Supports continuous auto-scan (every 2.5s), manual capture, or file upload testing without requiring a physical camera.

### 2. 🔐 Role-Based Access Control (RBAC) & Profiles
- **Super Admin (Society President / Committee)**: Full administrative oversight, financial ledger generation, ticket assignment, and system settings.
- **Security Guard / Staff**: Gate terminal operation, manual visitor check-ins, pass code validation, and technician dispatch.
- **Resident Member**: Unit dashboard, bill settlement, maintenance complaints, and guest pass pre-approvals.

### 3. 🛠️ Service Requests & Issue Tracking
- Complete ticketing workflow (`Open` &rarr; `In Progress` &rarr; `Resolved` &rarr; `Closed`).
- Category assignment (Plumbing, Electrical, Elevator, Noise, Security) with priority badges (Low, Medium, High, Urgent).
- Photo attachments and interactive resident-to-staff communication comments.

### 4. 📢 Announcement Notice Board
- Society-wide broadcasts with category filters (General, Maintenance, Security, Event, Emergency).
- Pin-to-top alert capability and circular/PDF attachments.

### 5. 💳 Maintenance Fee Collection & Invoicing
- Monthly billing cycles with automatic transaction ID generation (`TXN-...`).
- 1-click settlement simulation and printable digital receipt generation.

### 6. 🚗 Visitor & Vehicle Gate Passes
- Resident guest pre-approval generating unique 6-character access codes (`PASS88`, `PRIME1`).
- Guard check-in/out timestamps and vehicle plate logging.

### 7. 📊 Executive Intelligence Dashboard (Streamlit + Plotly)
- Running on Port 8501.
- **Complaint Resolution SLAs**: Ticket volume by category and resolution pipeline.
- **Revenue Inflows**: Monthly invoiced vs. collected dues breakdown.
- **Peak Hour Traffic**: Hourly entry spikes across the 24-hour cycle.
- **Biometric Accuracy Gauge**: Confidence score distribution across all gate scans.

---

## 🚀 Quick Start Guide

### 1. Requirements & Dependencies
Installed packages include:
- `Django >= 5.2 / 6.0`
- `djangorestframework`
- `opencv-contrib-python`
- `streamlit`
- `plotly`
- `pillow`
- `pandas`
- `numpy`

### 2. Setup Database & Pre-Trained Models
```bash
# Apply migrations
python manage.py migrate

# Seed sample data & train initial OpenCV biometric model
python seed_data.py
```

### 3. Start Development Servers
**Terminal 1 — Main Society Web Application:**
```bash
python manage.py runserver 8000
```
*Access at:* `http://localhost:8000`

**Terminal 2 — Streamlit Executive Analytics Dashboard:**
```bash
streamlit run admin_analytics.py --server.port 8501
```
*Access at:* `http://localhost:8501`

---

## 🔑 Demo Test Accounts

| Role | Username | Password | Unit / Description |
| :--- | :--- | :--- | :--- |
| **Super Admin** | `admin` | `admin123` | Committee Board President |
| **Security Guard** | `guard_vikram` | `guard123` | Gate Officer / Facility Dispatch |
| **Resident 1** | `john_doe` | `resident123` | Flat A-402, Emerald Tower (Enrolled Face) |
| **Resident 2** | `sarah_connor` | `resident123` | Flat B-204, Sapphire Tower (Enrolled Face) |
| **Resident 3** | `david_kim` | `resident123` | Flat C-301, Diamond Block |

*(The login screen also features 1-click credential quick-fill buttons for rapid evaluation!)*

---

## 🧪 Automated Test Suite
To run the automated verification checks:
```bash
python test_all_features.py
```
Outputs 8 validation passes across authentication, ticketing, billing, visitors, OpenCV face recognition, and REST APIs.
