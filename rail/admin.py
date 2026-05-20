from django.contrib import admin
from .models import Document, MovementHistory, Notification, OCRResult, OperationLog, RailwayTrack, Role, TrackSection, Train, UserProfile, Wagon

admin.site.register([Role, UserProfile, RailwayTrack, TrackSection, Train, Wagon, MovementHistory, Document, OCRResult, OperationLog, Notification])
