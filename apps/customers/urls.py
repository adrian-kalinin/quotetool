from django.urls import path

from apps.customers import views

app_name = "customers"

urlpatterns = [
    path("customers/", views.CustomerListView.as_view(), name="customer-list"),
    path("customers/new/", views.CustomerCreateView.as_view(), name="customer-create"),
    path("customers/<int:pk>/", views.CustomerDetailView.as_view(), name="customer-detail"),
    path("customers/<int:pk>/edit/", views.CustomerUpdateView.as_view(), name="customer-update"),
]
