from typing import cast

from django.contrib import messages
from django.db.models import Q
from django.db.models import QuerySet
from django.http import HttpResponse
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic import CreateView
from django.views.generic import DetailView
from django.views.generic import ListView
from django.views.generic import UpdateView

from apps.customers.forms import CustomerForm
from apps.customers.models import Customer
from apps.organizations.mixins import OrganizationAccessMixin


class CustomerListView(OrganizationAccessMixin, ListView):
    """List the active organization's customers, with search and pagination."""

    template_name = "customers/customer_list.html"
    partial_template_name = "customers/partials/customer_list_results.html"
    context_object_name = "customers"
    paginate_by = 10

    def get_queryset(self) -> QuerySet[Customer]:
        queryset = (
            Customer.objects.filter(organization=self.request.user.active_organization)
            .select_related("billing_address")
            .order_by("-created_at")
        )

        query = self.get_query()

        if query:
            queryset = queryset.filter(
                Q(company_name__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(email__icontains=query)
            )

        return queryset

    def get_query(self) -> str:
        return self.request.GET.get("q", "").strip()

    def get_template_names(self) -> list[str | None]:
        if self.request.htmx and self.request.htmx.target == "customer-list-container":
            return [self.partial_template_name]

        return [self.template_name]

    def get_context_data(self, **kwargs) -> dict[str, object]:
        context = super().get_context_data(**kwargs)

        context["query"] = self.get_query()

        return context


class CustomerDetailView(OrganizationAccessMixin, DetailView):
    """Show a single customer belonging to the active organization."""

    template_name = "customers/customer_detail.html"
    context_object_name = "customer"

    def get_queryset(self) -> QuerySet[Customer]:
        return Customer.objects.filter(organization=self.request.user.active_organization).select_related(
            "billing_address"
        )


class CustomerCreateView(OrganizationAccessMixin, CreateView):
    """Create a customer for the active organization."""

    template_name = "customers/customer_form.html"
    form_class = CustomerForm

    def form_valid(self, form: CustomerForm) -> HttpResponse:
        form.instance.organization = self.request.user.active_organization
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)

        messages.success(self.request, _("Customer created."))

        return response

    def get_success_url(self) -> str:
        customer = cast("Customer", self.object)
        return reverse("customers:customer-detail", kwargs={"pk": customer.pk})


class CustomerUpdateView(OrganizationAccessMixin, UpdateView):
    """Edit a customer belonging to the active organization."""

    template_name = "customers/customer_form.html"
    form_class = CustomerForm
    context_object_name = "customer"

    def get_queryset(self) -> QuerySet[Customer]:
        return Customer.objects.filter(organization=self.request.user.active_organization).select_related(
            "billing_address"
        )

    def form_valid(self, form: CustomerForm) -> HttpResponse:
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)

        messages.success(self.request, _("Customer updated."))

        return response

    def get_success_url(self) -> str:
        customer = cast("Customer", self.object)
        return reverse("customers:customer-detail", kwargs={"pk": customer.pk})
