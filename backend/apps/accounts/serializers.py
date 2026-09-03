from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from .models import User, StudentProfile, Role

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
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_first_login_required(self, obj: User) -> bool:
        if obj.role == Role.STUDENT and hasattr(obj, 'student_profile'):
            return obj.student_profile.first_login_required
        return False


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
            # EUID lookup ONLY (strictly matching CG-{ROLL} format, case-insensitive)
            euid_lookup = raw_id.upper()
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
