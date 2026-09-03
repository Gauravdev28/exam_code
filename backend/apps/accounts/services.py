import io
import re
import csv
import logging
from typing import List, Dict, Tuple, Any, Optional
import openpyxl
from django.db import transaction, IntegrityError
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

from .models import User, StudentProfile, AuditLog, Role

logger = logging.getLogger(__name__)

class EUIDService:
    """
    Deterministic, collision-safe Exam Unique ID (EUID) generation service.
    Generates standardized EUIDs derived from student academic roll numbers.
    Format: CG-{NORMALIZED_ROLL_NUMBER} (e.g. CG-BETN1AI25099)
    Strictly rejects collisions without generating numbered suffixes.
    """
    @staticmethod
    def normalize_roll_number(roll_number: str) -> str:
        if not roll_number:
            raise DRFValidationError("Roll number cannot be empty.")
        clean = roll_number.strip().upper()
        # Remove unwanted punctuation while preserving alphanumeric and hyphens/underscores
        normalized = re.sub(r'[^A-Z0-9_-]', '', clean)
        if not normalized:
            raise DRFValidationError("Roll number contains no valid alphanumeric characters.")
        return normalized

    @classmethod
    def generate_euid(cls, roll_number: str) -> str:
        normalized_roll = cls.normalize_roll_number(roll_number)
        return f"CG-{normalized_roll}"

    @classmethod
    def validate_unique_euid(cls, roll_number: str, exclude_user_id: Optional[str] = None) -> str:
        euid = cls.generate_euid(roll_number)
        qs = StudentProfile.objects.filter(euid=euid)
        if exclude_user_id:
            qs = qs.exclude(user__id=exclude_user_id)
        if qs.exists():
            raise DRFValidationError({"euid": f"A student with EUID '{euid}' already exists in the system."})
        return euid


class AuditService:
    """
    Immutable audit logging service recording administrative and security actions.
    """
    @staticmethod
    def extract_ip_address(request) -> Optional[str]:
        if not request:
            return None
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    @classmethod
    def log(
        cls,
        action: str,
        actor: Optional[User] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request=None
    ) -> AuditLog:
        ip = cls.extract_ip_address(request) if request else None
        safe_meta = metadata.copy() if metadata else {}
        
        # Ensure password or credential tokens never leak into audit metadata
        for sensitive_key in ['password', 'password_hash', 'current_password', 'new_password', 'token']:
            safe_meta.pop(sensitive_key, None)

        return AuditLog.objects.create(
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id else None,
            metadata=safe_meta,
            ip_address=ip
        )


class StudentService:
    """
    Domain service orchestrating student account lifecycle, verification, and creation.
    """
    @staticmethod
    def create_student(
        email: str,
        roll_number: str,
        actor: Optional[User] = None,
        request=None
    ) -> Tuple[User, StudentProfile]:
        clean_email = email.strip().lower()
        clean_roll = EUIDService.normalize_roll_number(roll_number)

        try:
            validate_email(clean_email)
        except DjangoValidationError:
            raise DRFValidationError({"email": "Enter a valid email address."})

        if User.objects.filter(email=clean_email).exists():
            raise DRFValidationError({"email": "A user with this email address already exists."})

        if StudentProfile.objects.filter(roll_number=clean_roll).exists():
            raise DRFValidationError({"roll_number": "A student with this roll number already exists."})

        euid = EUIDService.validate_unique_euid(clean_roll)

        try:
            with transaction.atomic():
                # Initial password is the exact student roll number (hashed securely)
                user = User.objects.create_user(
                    email=clean_email,
                    password=clean_roll,
                    role=Role.STUDENT,
                    is_active=True
                )

                profile = StudentProfile.objects.create(
                    user=user,
                    roll_number=clean_roll,
                    euid=euid,
                    first_login_required=True
                )

                AuditService.log(
                    action="STUDENT_CREATED",
                    actor=actor,
                    target_type="StudentProfile",
                    target_id=profile.id,
                    metadata={
                        "email": user.email,
                        "roll_number": profile.roll_number,
                        "euid": profile.euid
                    },
                    request=request
                )
        except IntegrityError:
            raise DRFValidationError({"roll_number": "A student with this roll number or EUID already exists."})

        return user, profile

    @staticmethod
    def update_student(
        student_profile: StudentProfile,
        email: Optional[str] = None,
        actor: Optional[User] = None,
        request=None
    ) -> StudentProfile:
        user = student_profile.user
        if not email:
            return student_profile

        clean_email = email.strip().lower()
        if clean_email == user.email:
            return student_profile

        try:
            validate_email(clean_email)
        except DjangoValidationError:
            raise DRFValidationError({"email": "Enter a valid email address."})

        if User.objects.filter(email=clean_email).exclude(id=user.id).exists():
            raise DRFValidationError({"email": "Email is already taken by another account."})

        with transaction.atomic():
            user.email = clean_email
            user.save(update_fields=['email', 'updated_at'])

            AuditService.log(
                action="STUDENT_UPDATED",
                actor=actor,
                target_type="StudentProfile",
                target_id=student_profile.id,
                metadata={"email": clean_email},
                request=request
            )

        return student_profile

    @staticmethod
    def set_student_status(
        student_profile: StudentProfile,
        is_active: bool,
        actor: Optional[User] = None,
        request=None
    ) -> StudentProfile:
        user = student_profile.user
        if user.is_active == is_active:
            return student_profile

        user.is_active = is_active
        user.save(update_fields=['is_active', 'updated_at'])

        action = "STUDENT_ENABLED" if is_active else "STUDENT_DISABLED"
        AuditService.log(
            action=action,
            actor=actor,
            target_type="StudentProfile",
            target_id=student_profile.id,
            metadata={"is_active": is_active, "email": user.email, "roll_number": student_profile.roll_number},
            request=request
        )

        return student_profile


class ImportService:
    """
    Bulk student import service supporting CSV and XLSX formats with a strict
    Validation -> Preview -> Admin Confirmation workflow.
    """
    MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
    ALLOWED_EXTENSIONS = ['.csv', '.xlsx']

    @classmethod
    def parse_file(cls, uploaded_file) -> List[Dict[str, str]]:
        filename = uploaded_file.name.lower()
        if not any(filename.endswith(ext) for ext in cls.ALLOWED_EXTENSIONS):
            raise DRFValidationError(f"Invalid file format. Supported formats: {', '.join(cls.ALLOWED_EXTENSIONS)}")

        if uploaded_file.size > cls.MAX_FILE_SIZE_BYTES:
            raise DRFValidationError(f"File size exceeds maximum allowed limit ({cls.MAX_FILE_SIZE_BYTES // (1024*1024)} MB).")

        rows: List[Dict[str, str]] = []

        if filename.endswith('.csv'):
            try:
                decoded_file = uploaded_file.read().decode('utf-8-sig')
                io_string = io.StringIO(decoded_file)
                reader = csv.reader(io_string)
                header_row = next(reader, None)
                if not header_row:
                    raise DRFValidationError("The uploaded CSV file is empty.")

                roll_idx, email_idx = cls._detect_columns(header_row)

                for line_num, row in enumerate(reader, start=2):
                    if not any(cell.strip() for cell in row):
                        continue  # Skip blank lines
                    roll = row[roll_idx].strip() if len(row) > roll_idx else ""
                    email = row[email_idx].strip() if len(row) > email_idx else ""
                    rows.append({"row_number": line_num, "roll_number": roll, "email": email})

            except UnicodeDecodeError:
                raise DRFValidationError("Failed to decode CSV file. Please ensure it is saved in UTF-8 encoding.")
            except Exception as e:
                if isinstance(e, DRFValidationError):
                    raise e
                raise DRFValidationError(f"Error parsing CSV file: {str(e)}")

        elif filename.endswith('.xlsx'):
            try:
                wb = openpyxl.load_workbook(uploaded_file, data_only=True)
                sheet = wb.active
                iter_rows = sheet.iter_rows(values_only=True)
                header_row = next(iter_rows, None)
                if not header_row:
                    raise DRFValidationError("The uploaded Excel workbook is empty.")

                header_list = [str(col).strip() if col is not None else "" for col in header_row]
                roll_idx, email_idx = cls._detect_columns(header_list)

                for line_num, row in enumerate(iter_rows, start=2):
                    if not row or not any(str(cell).strip() for cell in row if cell is not None):
                        continue
                    roll = str(row[roll_idx]).strip() if len(row) > roll_idx and row[roll_idx] is not None else ""
                    email = str(row[email_idx]).strip() if len(row) > email_idx and row[email_idx] is not None else ""
                    rows.append({"row_number": line_num, "roll_number": roll, "email": email})

            except Exception as e:
                if isinstance(e, DRFValidationError):
                    raise e
                raise DRFValidationError(f"Error parsing Excel spreadsheet: {str(e)}")

        if not rows:
            raise DRFValidationError("No student data rows found in the uploaded file.")

        return rows

    @staticmethod
    def _detect_columns(header_row: List[str]) -> Tuple[int, int]:
        roll_aliases = ['roll number', 'roll_number', 'roll', 'rollno', 'roll_no', 'student roll number', 'id']
        email_aliases = ['email', 'email address', 'email_address', 'student email', 'mail']

        roll_idx = -1
        email_idx = -1

        for idx, col in enumerate(header_row):
            col_clean = str(col).strip().lower()
            if col_clean in roll_aliases and roll_idx == -1:
                roll_idx = idx
            elif col_clean in email_aliases and email_idx == -1:
                email_idx = idx

        if roll_idx == -1 or email_idx == -1:
            raise DRFValidationError(
                "Required column headers not found. Expected headers: 'Roll Number' and 'Email'."
            )

        return roll_idx, email_idx

    @classmethod
    def validate_preview(cls, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validates parsed rows independently, checks database uniqueness and in-file duplicates,
        and generates an interactive preview report.
        """
        seen_rolls: Dict[str, int] = {}
        seen_emails: Dict[str, int] = {}

        # Collect non-empty rolls & emails for single-query bulk DB existence check
        candidate_rolls = set()
        candidate_emails = set()

        for r in rows:
            roll = r.get('roll_number', '').strip().upper()
            email = r.get('email', '').strip().lower()
            if roll:
                candidate_rolls.add(roll)
            if email:
                candidate_emails.add(email)

        existing_rolls = set(StudentProfile.objects.filter(roll_number__in=candidate_rolls).values_list('roll_number', flat=True))
        existing_emails = set(User.objects.filter(email__in=candidate_emails).values_list('email', flat=True))

        preview_rows = []
        valid_count = 0
        invalid_count = 0
        duplicate_count = 0

        for r in rows:
            row_num = r.get('row_number', 0)
            raw_roll = r.get('roll_number', '').strip()
            raw_email = r.get('email', '').strip()
            errors = []
            status_tag = "VALID"

            # 1. Roll Number Validation
            if not raw_roll:
                errors.append("Roll number is missing.")
            else:
                try:
                    norm_roll = EUIDService.normalize_roll_number(raw_roll)
                    euid_candidate = EUIDService.generate_euid(raw_roll)
                    if norm_roll in seen_rolls:
                        errors.append(f"Duplicate roll number in file (first seen at row {seen_rolls[norm_roll]}).")
                        status_tag = "DUPLICATE"
                    elif norm_roll in existing_rolls:
                        errors.append(f"Roll number already exists in system database (EUID: {euid_candidate}).")
                        status_tag = "DUPLICATE"
                    else:
                        seen_rolls[norm_roll] = row_num
                except DRFValidationError as ve:
                    errors.append(str(ve.detail[0] if isinstance(ve.detail, list) else ve.detail))

            # 2. Email Validation
            if not raw_email:
                errors.append("Email address is missing.")
            else:
                clean_email = raw_email.lower()
                try:
                    validate_email(clean_email)
                    if clean_email in seen_emails:
                        errors.append(f"Duplicate email address in file (first seen at row {seen_emails[clean_email]}).")
                        status_tag = "DUPLICATE"
                    elif clean_email in existing_emails:
                        errors.append("Email address already exists in system database.")
                        status_tag = "DUPLICATE"
                    else:
                        seen_emails[clean_email] = row_num
                except DjangoValidationError:
                    errors.append("Invalid email address format.")

            if errors:
                if status_tag != "DUPLICATE":
                    status_tag = "INVALID"
                if status_tag == "DUPLICATE":
                    duplicate_count += 1
                else:
                    invalid_count += 1
            else:
                valid_count += 1

            euid_preview = EUIDService.generate_euid(raw_roll) if raw_roll else ""

            preview_rows.append({
                "row_number": row_num,
                "roll_number": raw_roll,
                "email": raw_email,
                "euid": euid_preview,
                "status": status_tag,
                "errors": errors
            })

        return {
            "total_rows": len(rows),
            "valid_count": valid_count,
            "invalid_count": invalid_count,
            "duplicate_count": duplicate_count,
            "rows": preview_rows
        }

    @classmethod
    def execute_import(
        cls,
        items: List[Dict[str, str]],
        actor: Optional[User] = None,
        filename: Optional[str] = None,
        request=None
    ) -> Dict[str, Any]:
        """
        Executes verified student creation for all valid rows inside an atomic transaction.
        """
        created_students = []
        failed_rows = []

        with transaction.atomic():
            for item in items:
                roll = item.get('roll_number', '').strip()
                email = item.get('email', '').strip().lower()

                try:
                    user, profile = StudentService.create_student(
                        email=email,
                        roll_number=roll,
                        actor=actor,
                        request=request
                    )
                    created_students.append({
                        "id": str(profile.id),
                        "email": user.email,
                        "roll_number": profile.roll_number,
                        "euid": profile.euid
                    })
                except Exception as e:
                    failed_rows.append({
                        "roll_number": roll,
                        "email": email,
                        "error": str(e)
                    })

            AuditService.log(
                action="STUDENT_IMPORT_COMPLETED",
                actor=actor,
                target_type="StudentProfile",
                metadata={
                    "filename": filename,
                    "total_submitted": len(items),
                    "created_count": len(created_students),
                    "failed_count": len(failed_rows)
                },
                request=request
            )

        return {
            "total_submitted": len(items),
            "created_count": len(created_students),
            "failed_count": len(failed_rows),
            "created_students": created_students,
            "failed_rows": failed_rows
        }
