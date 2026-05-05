from django.contrib import admin

from .models import StudentSource, StudentSourceInteraction


@admin.register(StudentSource)
class StudentSourceAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'user',
        'subject',
        'source_type',
        'status',
        'file_size',
        'created_at',
    )
    list_filter = ('source_type', 'status', 'subject', 'created_at')
    search_fields = ('title', 'original_filename', 'user__email')
    readonly_fields = (
        'original_filename',
        'file_size',
        'mime_type',
        'extension',
        'created_at',
        'updated_at',
    )
    autocomplete_fields = ('user', 'subject')


@admin.register(StudentSourceInteraction)
class StudentSourceInteractionAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'source',
        'character',
        'action',
        'status',
        'result_type',
        'result_id',
        'created_at',
    )
    list_filter = ('character', 'action', 'status', 'created_at')
    search_fields = ('user__email', 'source__title', 'message')
    autocomplete_fields = ('user', 'source')
    readonly_fields = ('created_at', 'updated_at')
