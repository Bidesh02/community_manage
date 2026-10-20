from django.urls import path
from . import views

urlpatterns = [
    # Auth & Profile
    path('', views.dashboard_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('profile/', views.profile_view, name='profile'),
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # Notices
    path('notices/', views.notice_list_view, name='notice_list'),
    path('notices/create/', views.notice_create_view, name='notice_create'),
    path('notices/<int:pk>/delete/', views.notice_delete_view, name='notice_delete'),

    # Tickets / Complaints
    path('tickets/', views.ticket_list_view, name='ticket_list'),
    path('tickets/create/', views.ticket_create_view, name='ticket_create'),
    path('tickets/<int:pk>/', views.ticket_detail_view, name='ticket_detail'),
    path('tickets/<int:pk>/status/', views.ticket_update_status_view, name='ticket_update_status'),
    path('tickets/<int:pk>/comment/', views.ticket_comment_create_view, name='ticket_comment_create'),

    # Maintenance & Fees
    path('maintenance/', views.maintenance_list_view, name='maintenance_list'),
    path('maintenance/<int:pk>/pay/', views.maintenance_pay_view, name='maintenance_pay'),
    path('maintenance/generate/', views.maintenance_generate_view, name='maintenance_generate'),

    # Visitors
    path('visitors/', views.visitor_list_view, name='visitor_list'),
    path('visitors/checkin/', views.visitor_checkin_view, name='visitor_checkin'),
    path('visitors/preapprove/', views.visitor_preapprove_view, name='visitor_preapprove'),
    path('visitors/<int:pk>/checkout/', views.visitor_checkout_view, name='visitor_checkout'),

    # OpenCV Real-Time Face Gate
    path('gate/terminal/', views.face_terminal_view, name='face_terminal'),
    path('gate/logs/', views.biometric_logs_view, name='biometric_logs'),
    path('gate/retrain/', views.retrain_face_model_view, name='retrain_face_model'),

    # REST APIs
    path('api/face-recognize/', views.api_face_recognize, name='api_face_recognize'),
    path('api/quick-stats/', views.api_quick_stats, name='api_quick_stats'),
]
