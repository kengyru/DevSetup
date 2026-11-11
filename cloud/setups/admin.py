from django.contrib import admin

from .models import Setup


@admin.register(Setup)
class SetupAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "user",
        "format_version",
        "created_at",
        "updated_at",
    )
    list_filter = ("format_version", "created_at")
    search_fields = ("name", "user__email", "id")
    readonly_fields = (
        "id",
        "user",
        "name",
        "format_version",
        "data",
        "created_at",
        "updated_at",
    )
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        # New setups must go through the API so validation always runs.
        return False
