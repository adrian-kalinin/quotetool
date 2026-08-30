from django.urls import path

from apps.core import views

app_name = "core"

urlpatterns = [
    path("messages/", views.MessagesView.as_view(), name="hx-messages"),
    path("set-language/", views.SetLanguageView.as_view(), name="set-language"),
]
