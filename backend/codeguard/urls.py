from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Core system endpoints (health check, system info)
    path('api/v1/', include('apps.core.urls')),
    
    # Accounts, Authentication & Student Management endpoints
    path('api/v1/', include('apps.accounts.urls')),
    
    # Question Bank & Versioning endpoints
    path('api/v1/', include('apps.questions.urls')),
    
    # Assessment Engine & Test Attempt endpoints
    path('api/v1/', include('apps.assessments.urls')),
    
    # Code Execution & Evaluation Engine endpoints
    path('api/v1/', include('apps.evaluator.urls')),
    
    # AI Proctoring & Anti-Cheating endpoints
    path('api/v1/', include('apps.proctoring.urls')),
    
    # Results, Analytics & Reporting endpoints
    path('api/v1/', include('apps.results.urls')),
    
    # Data Retention, Privacy Compliance & Legal Holds endpoints
    path('api/v1/', include('apps.retention.urls')),
    # path('api/v1/audit/', include('apps.audit.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
