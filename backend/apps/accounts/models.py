import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.core.exceptions import PermissionDenied, ValidationError
from apps.core.models import UUIDModel, TimeStampedModel

class Role(models.TextChoices):
    ADMIN = 'ADMIN', 'Admin'
    STUDENT = 'STUDENT', 'Student'
    PROCTOR = 'PROCTOR', 'Proctor'


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
    admin_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        verbose_name="Admin ID",
        help_text="Authoritative unique administrative identifier."
    )
    display_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Display Name",
        help_text="Authoritative user display name."
    )
    first_login_required = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="First Login Password Change Required",
        help_text="Mandates password change upon next login."
    )
    primary_admin_marker = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        unique=True,
        default=None,
        db_index=True,
        verbose_name="Primary Admin Singleton Marker",
        help_text="Database-level singleton constraint. Exactly one row in the database may have marker='PRIMARY'; all other rows are NULL."
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
            models.Index(fields=['admin_id']),
        ]
        constraints = [
            models.UniqueConstraint(
                models.Case(
                    models.When(models.Q(role=Role.ADMIN) & ~models.Q(admin_id=''), then=models.F('admin_id')),
                    default=models.Value(None),
                    output_field=models.CharField(max_length=64, null=True),
                ),
                name='unique_admin_id_for_admins'
            ),
            models.CheckConstraint(
                condition=models.Q(primary_admin_marker__isnull=True) | models.Q(primary_admin_marker='PRIMARY', role=Role.ADMIN),
                name='primary_admin_marker_valid_state'
            ),
        ]

    def __str__(self):
        return f"{self.email} ({self.role})"

    def clean(self):
        super().clean()
        if self.email:
            self.email = self.email.strip().lower()
        if self.primary_admin_marker is not None and self.primary_admin_marker != 'PRIMARY':
            raise ValidationError({"primary_admin_marker": "primary_admin_marker must be NULL or 'PRIMARY'."})
        if self.primary_admin_marker == 'PRIMARY' and self.role != Role.ADMIN:
            raise ValidationError({"primary_admin_marker": "Only accounts with role='ADMIN' may have primary_admin_marker='PRIMARY'."})

    def save(self, *args, **kwargs):
        # 1. Normalize email before persistence
        if self.email:
            self.email = self.email.strip().lower()

        # 2. Enforce primary_admin_marker semantic invariant
        if self.primary_admin_marker is not None and self.primary_admin_marker != 'PRIMARY':
            raise ValidationError({"primary_admin_marker": "primary_admin_marker must be NULL or 'PRIMARY'."})

        # 3. Creation Lifecycle (self._state.adding == True)
        if self._state.adding:
            if self.role == Role.ADMIN and not self.admin_id:
                if self.email == 'gauravagldeveloper28@gmail.com' and not User.objects.filter(admin_id='EUAD-GAURAV-099').exists():
                    self.admin_id = 'EUAD-GAURAV-099'
                else:
                    from .services import AdminIdService
                    self.admin_id = AdminIdService.generate_next_admin_id()
            if self.role == Role.ADMIN and self.admin_id == 'EUAD-GAURAV-099' and self.primary_admin_marker is None:
                if not User.objects.filter(primary_admin_marker='PRIMARY').exists():
                    self.primary_admin_marker = 'PRIMARY'
            if not self.display_name:
                if self.email == 'gauravagldeveloper28@gmail.com':
                    self.display_name = 'Gaurav Agarwal'
                else:
                    prefix = self.email.split('@')[0]
                    cleaned = ''.join(c if c.isalpha() else ' ' for c in prefix).strip().title()
                    self.display_name = cleaned or ("Administrator" if self.role == Role.ADMIN else "Student")

        # 4. Update Immutability Lifecycle (not self._state.adding and self.pk)
        if not self._state.adding and self.pk:
            existing = User.objects.filter(pk=self.pk).values(
                'id', 'email', 'admin_id', 'display_name', 'role', 'primary_admin_marker', 'is_active', 'password'
            ).first()

            if existing:
                # Administrator-Scoped Immutability (Unconditional equality: OLD == NEW)
                if existing['role'] == Role.ADMIN or self.role == Role.ADMIN:
                    if self.email != existing['email']:
                        raise PermissionDenied("Administrator email address is strictly immutable.")
                    if self.admin_id != existing['admin_id']:
                        raise PermissionDenied("Administrator Admin ID is strictly immutable.")
                    if self.display_name != existing['display_name']:
                        raise PermissionDenied("Administrator display name is strictly immutable.")
                    if self.role != existing['role']:
                        raise PermissionDenied("Administrator role cannot be altered.")
                    if self.primary_admin_marker != existing['primary_admin_marker']:
                        raise PermissionDenied("Primary Administrator marker cannot be altered.")

                # Primary Admin Deactivation Protection
                if existing['primary_admin_marker'] == 'PRIMARY' and not self.is_active:
                    raise PermissionDenied("The Primary Administrator account cannot be deactivated.")

                # Non-Admin Promotion Protection
                if existing['role'] != Role.ADMIN and self.primary_admin_marker == 'PRIMARY':
                    raise PermissionDenied("Non-administrator account cannot be designated as Primary Administrator.")

                # Password Integrity & Immutability Invariant:
                # Normal user updates must never mutate existing password hash.
                # Only explicit set_password() (which sets instance._password) or explicit 'password' in update_fields may alter it.
                update_fields = kwargs.get('update_fields')
                if update_fields is not None:
                    if 'password' not in update_fields:
                        self.password = existing['password']
                else:
                    if not getattr(self, '_password', None) and existing.get('password'):
                        self.password = existing['password']

        # 5. Prevent Saving Plaintext Passwords / Prevent Double Hashing
        # If a raw password string without algorithm identifier is assigned, securely hash it.
        if self.password and not self.password.startswith('!') and '$' not in self.password:
            from django.contrib.auth.hashers import make_password
            self.password = make_password(self.password)

        super().save(*args, **kwargs)

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN

    @property
    def is_student(self) -> bool:
        return self.role == Role.STUDENT

    @property
    def is_primary_admin(self) -> bool:
        return self.role == Role.ADMIN and self.primary_admin_marker == 'PRIMARY'

    @property
    def first_name(self) -> str:
        parts = self.display_name.split()
        return parts[0] if parts else "Administrator"

    def delete(self, *args, **kwargs):
        if self.is_primary_admin:
            raise PermissionDenied("The Primary Administrator account is permanently protected and cannot be deleted.")
        return super().delete(*args, **kwargs)


class AdminSequence(UUIDModel, TimeStampedModel):
    """
    Transactional sequence tracker ensuring atomic, race-condition-free Admin ID generation.
    """
    last_sequence = models.PositiveIntegerField(default=2)

    class Meta:
        verbose_name = 'Admin Sequence'
        verbose_name_plural = 'Admin Sequences'

    def __str__(self):
        return f"AdminSequence(last={self.last_sequence})"


class Section(UUIDModel, TimeStampedModel):
    """
    Academic Section entity for student classification and assessment targeting.
    Normalized code, human-readable name, active state, and audit-safe timestamps.
    """
    code = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        verbose_name="Section Code",
        help_text="Unique normalized academic section code (e.g. AIML-A, CSE-B)."
    )
    name = models.CharField(
        max_length=128,
        verbose_name="Section Name",
        help_text="Human-readable section title (e.g. Artificial Intelligence & Machine Learning Section A)."
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Is Active",
        help_text="Designates whether this section is active for new student enrollment and assessment targeting."
    )

    class Meta:
        verbose_name = 'Section'
        verbose_name_plural = 'Sections'
        ordering = ['code']
        indexes = [
            models.Index(fields=['code', 'is_active']),
        ]

    def __str__(self):
        return f"{self.code} ({self.name})"

    def clean(self):
        super().clean()
        if self.code:
            self.code = self.code.strip().upper()
        if self.name:
            self.name = self.name.strip()

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        if self.name:
            self.name = self.name.strip()
        super().save(*args, **kwargs)


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
    section = models.ForeignKey(
        Section,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students',
        verbose_name="Academic Section",
        help_text="Academic section classification for student."
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
            models.Index(fields=['section']),
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
