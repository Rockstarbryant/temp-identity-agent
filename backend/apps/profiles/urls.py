from django.urls import path

from apps.profiles import views

urlpatterns = [
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("preferences/", views.PreferencesView.as_view(), name="preferences"),
    path("profile/entries/<str:key>/", views.ProfileEntryView.as_view(), name="profile-entry"),
    path("email-connection/", views.EmailConnectionView.as_view(), name="email-connection"),
    path("email-connection/test/", views.EmailConnectionTestView.as_view(), name="email-connection-test"),
    path("email-connection/gmail/authorize/", views.GmailAuthorizeView.as_view(), name="gmail-authorize"),
    path("email-connection/gmail/callback/", views.GmailCallbackView.as_view(), name="gmail-callback"),
]
