import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.core.exceptions import PermissionDenied
from apps.core.models import UUIDModel, TimeStampedModel

class Role(models.TextChoices):
    ADMIN = 'ADMIN', 'Admin'
    STUDENT = 'STUDENT', 'Student'


class UserManager(BaseUserManager):
    """
    Custom user manager supporting email-based authentication.
    """
    def create_user(self, email, password=None, role=Role.STUDENT, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        
        email = self.normalize_email(email).lower()
        extra_fields.setdefault('is_active', True)
        
        user = self.model(
            email=email,
            role=role,
            **extra_fields
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', Role.ADMIN)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, UUIDModel, TimeStampedModel):
    """
    Primary User model for CODEGUARD.
    Employs email as unique identifier, role-based authorization, and UUID primary keys.
    """
    email = models.EmailField(
        unique=True,
        db_index=True,
        max_length=255,
        verbose_name="Email Address"
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
        db_index=True,
        verbose_name="User Role"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Active Status",
        help_text="Designates whether this user account is active and permitted to authenticate."
    )
    is_staff = models.BooleanField(
        default=False,
        verbose_name="Staff Status",
        help_text="Designates whether the user can log into the Django admin site."
    )

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', 'is_active']),
            models.Index(fields=['role', 'is_active']),
        ]

    def __str__(self):
        return f"{self.email} ({self.role})"

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN or self.is_staff or self.is_superuser

    @property
    def is_student(self) -> bool:
        return self.role == Role.STUDENT


class StudentProfile(UUIDModel, TimeStampedModel):
    """
    Student-specific profile containing official academic roll number,
    generated Exam Unique ID (EUID), and first-login password enforcement flag.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='student_profile',
        verbose_name="Associated User"
    )
    roll_number = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name="Academic Roll Number",
        help_text="Unique student registration/roll number."
    )
    euid = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name="Exam Unique ID (EUID)",
        help_text="Deterministic, collision-safe exam unique identifier."
    )
    first_login_required = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="First Login Password Change Required",
        help_text="Mandates immediate password reset before student can access platform assessments."
    )

    class Meta:
        verbose_name = 'Student Profile'
        verbose_name_plural = 'Student Profiles'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['roll_number']),
            models.Index(fields=['euid']),
            models.Index(fields=['first_login_required']),
        ]

    def __str__(self):
        return f"{self.roll_number} [{self.euid}] - {self.user.email}"


class AuditLog(UUIDModel):
    """
    Application-enforced immutable audit log recording administrative, authentication,
    and student lifecycle mutations. Updates and deletions are strictly rejected.
    """
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name="Acting User"
    )
    action = models.CharField(
        max_length=64,
        db_index=True,
        verbose_name="Action Type"
    )
    target_type = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        verbose_name="Target Entity Type"
    )
    target_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Target Entity ID"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Event Metadata"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP Address"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Timestamp"
    )

    class Meta:
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['actor', 'created_at']),
            models.Index(fields=['target_type', 'target_id']),
        ]

    def __str__(self):
        actor_email = self.actor.email if self.actor else "SYSTEM"
        return f"[{self.created_at}] {actor_email} -> {self.action}"

    def save(self, *args, **kwargs):
        if not self._state.adding and self.pk:
            raise PermissionDenied("Audit logs are strictly immutable and cannot be updated.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("Audit logs are append-only and cannot be deleted.")
