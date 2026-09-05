from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from .models import User, StudentProfile, Role, AuditLog

class StudentProfileSerializer(serializers.ModelSerializer):
    """
    Representation of the student profile entity.
    """
    class Meta:
        model = StudentProfile
        fields = [
            'id',
            'roll_number',
            'euid',
            'first_login_required',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class UserSerializer(serializers.ModelSerializer):
    """
    Safe public user representation.
    Strictly excludes sensitive fields such as password hash, security tokens, or permissions internals.
    """
    student_profile = StudentProfileSerializer(read_only=True)
    first_login_required = serializers.SerializerMethodField()
    admin_id = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    first_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'role',
            'is_active',
            'is_staff',
            'first_login_required',
            'student_profile',
            'admin_id',
            'display_name',
            'first_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_first_login_required(self, obj: User) -> bool:
        if obj.role == Role.STUDENT and hasattr(obj, 'student_profile') and obj.student_profile:
            return obj.student_profile.first_login_required or getattr(obj, 'first_login_required', False)
        return getattr(obj, 'first_login_required', False)


class AdministratorSerializer(serializers.ModelSerializer):
    """
    Representation of an Administrator user for the Admin Management area.
    """
    admin_id = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    is_primary = serializers.SerializerMethodField()
    is_primary_admin = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'admin_id',
            'email',
            'display_name',
            'first_name',
            'role',
            'is_active',
            'is_primary',
            'is_primary_admin',
            'first_login_required',
            'created_at',
            'updated_at',
            'last_login',
        ]
        read_only_fields = fields

    def get_is_primary(self, obj: User) -> bool:
        return getattr(obj, 'is_primary_admin', False)


class UpdateAdministratorSerializer(serializers.Serializer):
    """
    Decommissioned: Administrator identity and account details are immutable. Editing is prohibited.
    """
    display_name = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)

    def validate(self, attrs):
        raise serializers.ValidationError("Administrator identity and account details are immutable. Editing is prohibited.")


class ResetPasswordSerializer(serializers.Serializer):
    """
    Serializer for administrative password reset.
    Requires an administrative justification, temporary password, and confirmation.
    """
    reason = serializers.CharField(
        required=True,
        min_length=3,
        max_length=500,
        trim_whitespace=True,
        help_text="Administrative justification for the password reset."
    )
    temporary_password = serializers.CharField(
        required=False,
        allow_blank=True,
        default=None,
        write_only=True,
        min_length=8,
        style={'input_type': 'password'},
        help_text="Optional custom temporary password."
    )
    confirm_temporary_password = serializers.CharField(
        required=False,
        allow_blank=True,
        default=None,
        write_only=True,
        min_length=8,
        style={'input_type': 'password'},
        help_text="Confirmation of the optional custom temporary password."
    )

    def validate(self, attrs):
        temp_pwd = attrs.get('temporary_password')
        confirm_pwd = attrs.get('confirm_temporary_password')
        if temp_pwd or confirm_pwd:
            if not temp_pwd or not confirm_pwd:
                raise serializers.ValidationError({
                    "confirm_temporary_password": "Both temporary password and confirmation are required if setting manually."
                })
            if temp_pwd != confirm_pwd:
                raise serializers.ValidationError({
                    "confirm_temporary_password": "Temporary password and confirmation do not match."
                })
            validate_password(temp_pwd)
        return attrs


class AuditLogSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for the immutable Security Audit Trail.
    Strictly sanitizes and never returns sensitive tokens, credentials, or hashes.
    """
    actor_id = serializers.UUIDField(source='actor.id', read_only=True)
    actor_name = serializers.SerializerMethodField()
    actor_admin_id = serializers.SerializerMethodField()
    target_identity = serializers.SerializerMethodField()
    target_email = serializers.SerializerMethodField()
    target_role = serializers.SerializerMethodField()
    reason = serializers.SerializerMethodField()
    result = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'action',
            'actor_id',
            'actor_name',
            'actor_admin_id',
            'target_type',
            'target_id',
            'target_identity',
            'target_email',
            'target_role',
            'reason',
            'result',
            'metadata',
            'ip_address',
            'created_at',
        ]
        read_only_fields = fields

    def get_actor_name(self, obj: AuditLog) -> str:
        if obj.metadata and 'actor_name' in obj.metadata:
            return obj.metadata['actor_name']
        if obj.actor:
            return obj.actor.display_name
        return "SYSTEM"

    def get_actor_admin_id(self, obj: AuditLog) -> str:
        if obj.metadata and 'actor_admin_id' in obj.metadata:
            return obj.metadata['actor_admin_id']
        if obj.actor and getattr(obj.actor, 'admin_id', None):
            return obj.actor.admin_id
        return ""

    def get_target_identity(self, obj: AuditLog) -> str:
        if not obj.metadata:
            return ""
        return obj.metadata.get('target_identity') or obj.metadata.get('euid') or obj.metadata.get('admin_id') or obj.metadata.get('roll_number') or ""

    def get_target_email(self, obj: AuditLog) -> str:
        if not obj.metadata:
            return ""
        return obj.metadata.get('target_email') or obj.metadata.get('email') or ""

    def get_target_role(self, obj: AuditLog) -> str:
        if not obj.metadata:
            return ""
        return obj.metadata.get('target_role') or ""

    def get_reason(self, obj: AuditLog) -> str:
        if not obj.metadata:
            return ""
        return obj.metadata.get('reason') or ""

    def get_result(self, obj: AuditLog) -> str:
        if not obj.metadata:
            return "SUCCESS"
        return obj.metadata.get('result', "SUCCESS")



class CreateAdministratorSerializer(serializers.Serializer):
    """
    Validation schema for creating a new Administrator account.
    """
    email = serializers.EmailField()
    display_name = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(required=False, allow_blank=True, default=None, write_only=True, min_length=8)
    is_active = serializers.BooleanField(default=True)

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("An account with this email address already exists.")
        return email

    def validate(self, attrs):
        pwd = attrs.get('password')
        confirm_pwd = attrs.get('confirm_password')
        if confirm_pwd is not None and pwd != confirm_pwd:
            raise serializers.ValidationError({"confirm_password": "Password and confirmation do not match."})
        validate_password(pwd)
        return attrs


class StudentDetailSerializer(serializers.ModelSerializer):
    """
    Admin-level detailed student representation joining User and StudentProfile fields.
    """
    user_id = serializers.UUIDField(source='user.id', read_only=True)
    email = serializers.EmailField(source='user.email')
    is_active = serializers.BooleanField(source='user.is_active')
    role = serializers.CharField(source='user.role', read_only=True)

    class Meta:
        model = StudentProfile
        fields = [
            'id',
            'user_id',
            'email',
            'role',
            'roll_number',
            'euid',
            'is_active',
            'first_login_required',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'user_id', 'role', 'roll_number', 'euid', 'created_at', 'updated_at']


class CreateStudentSerializer(serializers.Serializer):
    """
    Serializer for individual student creation by an administrator.
    """
    email = serializers.EmailField(required=True)
    roll_number = serializers.CharField(required=True, max_length=64)


class UpdateStudentSerializer(serializers.Serializer):
    """
    Serializer for updating student profile.
    Only email is permitted to be modified.
    Roll number, EUID, role, and internal fields are strictly immutable.
    """
    email = serializers.EmailField(required=True)

    def validate(self, attrs):
        # Explicitly reject attempts to modify immutable identity or server-controlled fields
        immutable_fields = [
            'roll_number',
            'euid',
            'role',
            'user_id',
            'id',
            'is_active',
            'first_login_required',
            'password',
        ]
        errors = {}
        for field in immutable_fields:
            if field in self.initial_data:
                field_label = field.replace('_', ' ').capitalize()
                errors[field] = [f"{field_label} cannot be modified after student creation."]

        if errors:
            raise ValidationError(errors)

        return attrs


class BulkImportConfirmSerializer(serializers.Serializer):
    """
    Payload containing verified student rows to create in batch.
    """
    filename = serializers.CharField(required=False, allow_blank=True, default="import.csv")
    students = CreateStudentSerializer(many=True, required=True)


class ChangePasswordSerializer(serializers.Serializer):
    """
    Secure password change serializer with Django validator integration and first_login satisfaction.
    """
    current_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    new_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    confirm_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )

    def validate(self, attrs):
        user = self.context.get('request').user
        current_password = attrs.get('current_password')
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')

        if not user.check_password(current_password):
            raise ValidationError({"current_password": "The current password provided is incorrect."})

        if new_password != confirm_password:
            raise ValidationError({"confirm_password": "New password and confirmation do not match."})

        if current_password == new_password:
            raise ValidationError({"new_password": "New password must be different from current password."})

        # Run Django's configured password validators
        validate_password(new_password, user=user)

        return attrs


class LoginSerializer(serializers.Serializer):
    """
    Dual-Authentication Login Serializer.
    Supports strictly: Email + Password OR EUID + Password.
    Roll Number is NOT a login identifier.
    """
    identifier = serializers.CharField(
        required=False,
        help_text="Student Email OR Exam Unique ID (EUID)"
    )
    email = serializers.CharField(
        required=False,
        help_text="Alternative email field for backward compatibility"
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )

    def validate(self, attrs):
        raw_id = (attrs.get('identifier') or attrs.get('email') or '').strip()
        password = attrs.get('password')

        if not raw_id or not password:
            raise ValidationError("Both login identifier (Email or EUID) and password are required.")

        user_obj = None

        # Determine if login identifier is Email or EUID
        if '@' in raw_id:
            email_lookup = raw_id.lower()
            try:
                user_obj = User.objects.select_related('student_profile').get(email=email_lookup)
            except User.DoesNotExist:
                user_obj = None
        else:
            raw_upper = raw_id.upper()
            if raw_upper.startswith('EUAD-') or raw_upper.startswith('CG-ADM-'):
                raise AuthenticationFailed(
                    detail="Admin ID is an identity display identifier, not a login credential. Please sign in with your registered email.",
                    code="ADMIN_ID_NOT_LOGIN_CREDENTIAL"
                )
            # EUID lookup ONLY (strictly matching CG-{ROLL} format, case-insensitive)
            euid_lookup = raw_upper
            try:
                profile = StudentProfile.objects.select_related('user').get(euid=euid_lookup)
                user_obj = profile.user
            except StudentProfile.DoesNotExist:
                user_obj = None

        if user_obj and not user_obj.is_active:
            raise AuthenticationFailed(
                detail="Your account has been disabled. Please contact system administrator.",
                code="ACCOUNT_DISABLED"
            )

        if not user_obj:
            raise AuthenticationFailed(
                detail="Invalid login credentials.",
                code="INVALID_CREDENTIALS"
            )

        # Authenticate with resolved user email
        user = authenticate(
            request=self.context.get('request'),
            username=user_obj.email,
            password=password
        )

        if not user:
            raise AuthenticationFailed(
                detail="Invalid login credentials.",
                code="INVALID_CREDENTIALS"
            )

        if not user.is_active:
            raise AuthenticationFailed(
                detail="Your account has been disabled. Please contact system administrator.",
                code="ACCOUNT_DISABLED"
            )

        attrs['user'] = user
        return attrs
