from django.urls import path

from apps.registration.views import (
    RegistrationJobAnswerView,
    RegistrationJobCancelView,
    RegistrationJobClearFinishedView,
    RegistrationJobDetailView,
    RegistrationJobListCreateView,
    RegistrationJobLiveInputView,
    RegistrationJobLiveView,
    RegistrationJobResumeView,
    RegistrationJobRetryView,
)

urlpatterns = [
    path("registration-jobs/", RegistrationJobListCreateView.as_view(), name="job-list-create"),
    path("registration-jobs/clear-finished/", RegistrationJobClearFinishedView.as_view(), name="job-clear-finished"),
    path("registration-jobs/<uuid:pk>/", RegistrationJobDetailView.as_view(), name="job-detail"),
    path("registration-jobs/<uuid:pk>/resume/", RegistrationJobResumeView.as_view(), name="job-resume"),
    path("registration-jobs/<uuid:pk>/live/", RegistrationJobLiveView.as_view(), name="job-live"),
    path("registration-jobs/<uuid:pk>/live/input/", RegistrationJobLiveInputView.as_view(), name="job-live-input"),
    path("registration-jobs/<uuid:pk>/questions/<uuid:qid>/answer/", RegistrationJobAnswerView.as_view(), name="job-answer"),
    path("registration-jobs/<uuid:pk>/cancel/", RegistrationJobCancelView.as_view(), name="job-cancel"),
    path("registration-jobs/<uuid:pk>/retry/", RegistrationJobRetryView.as_view(), name="job-retry"),
]
