from django.contrib.auth.views import LogoutView
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='home'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('trains/', views.TrainList.as_view(), name='trains'),
    path('trains/create/', views.TrainCreate.as_view(), name='train_create'),
    path('trains/<int:pk>/', views.TrainDetail.as_view(), name='train_detail'),
    path('trains/<int:pk>/edit/', views.TrainUpdate.as_view(), name='train_edit'),
    path('trains/<int:pk>/depart/', views.depart_train, name='train_depart'),
    path('wagons/', views.WagonList.as_view(), name='wagons'),
    path('wagons/create/', views.WagonCreate.as_view(), name='wagon_create'),
    path('wagons/<int:pk>/', views.WagonDetail.as_view(), name='wagon_detail'),
    path('wagons/<int:pk>/edit/', views.WagonUpdate.as_view(), name='wagon_edit'),
    path('tracks/', views.tracks, name='tracks'),
    path('track-map/', views.track_map, name='track_map'),
    path('track-map/drag-wagon/', views.track_map_drag_wagon, name='track_map_drag_wagon'),
    path('documents/', views.documents, name='documents'),
    path('documents/upload/', views.upload_document, name='document_upload'),
    path('documents/<int:pk>/ocr/', views.document_ocr, name='document_ocr'),
    path('reports/', views.reports, name='reports'),
    path('notifications/', views.notifications, name='notifications'),
    path('admin-panel/', views.admin_panel, name='admin_panel'),
]
