from django.urls import path

from apps.pages import views

app_name = "pages"

urlpatterns = [
    path("", views.LandingPageView.as_view(), name="landing"),
]
