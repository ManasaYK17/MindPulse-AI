from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('register/', views.register, name='register'),
    path('logout/', auth_views.LogoutView.as_view(next_page='chatbot'), name='logout'),
    path('chatbot/', views.chatbot, name='chatbot'),
    path('assessment/', views.assessment, name='assessment'),
    path('assessment/result/', views.assessment_result, name='assessment_result'),
    path('recommendations/', views.recommendations, name='recommendations'),
    path('peer-support/', views.peer_support, name='peer_support'),
    path('future-you/', views.future_you, name='future_you'),
    path('appointments/', views.appointment_list, name='appointment_list'),
    path('book-appointment/', views.book_appointment, name='book_appointment'),
    path('profile/', views.profile, name='profile'),
    path('wellness/', views.wellness_activity, name='wellness_activity'),
    path('mark-task/<int:task_id>/', views.mark_task_completed, name='mark_task_completed'),
    # Admin features
    path('admin-panel/', views.admin_panel, name='admin_panel'),
    path('admin-panel/add-counselor/', views.add_counselor, name='add_counselor'),
    path('admin-panel/add-question/', views.add_question, name='add_question'),
    path('admin-panel/add-task/', views.add_task, name='add_task'),
]
