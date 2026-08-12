from django.urls import path

from apps.registration.views import (
    RegistrationJobCancelView,
    RegistrationJobDetailView,
    RegistrationJobListCreateView,
    RegistrationJobResumeView,
)

urlpatterns = [
    path("registration-jobs/", RegistrationJobListCreateView.as_view(), name="job-list-create"),
    path("registration-jobs/<uuid:pk>/", RegistrationJobDetailView.as_view(), name="job-detail"),
    path("registration-jobs/<uuid:pk>/resume/", RegistrationJobResumeView.as_view(), name="job-resume"),
    path("registration-jobs/<uuid:pk>/cancel/", RegistrationJobCancelView.as_view(), name="job-cancel"),
]
