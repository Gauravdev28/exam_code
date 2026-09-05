import os
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.accounts.models import User, Role
from apps.accounts.services import AdminIdService

class Command(BaseCommand):
    help = 'Idempotently creates or verifies the primary development administrator account.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            default=os.getenv('ADMIN_BOOTSTRAP_EMAIL', 'gauravagldeveloper28@gmail.com'),
            help='Administrator email address.'
        )
        parser.add_argument(
            '--password',
            type=str,
            default=os.getenv('ADMIN_BOOTSTRAP_PASSWORD', 'Gaurav@123'),
            help='Administrator password.'
        )
        parser.add_argument(
            '--reset-password',
            action='store_true',
            help='Force password reset on existing account.'
        )

    def handle(self, *args, **options):
        email = options['email'].lower().strip()
        password = options['password']
        force_reset = options['reset_password']

        user = User.objects.filter(email=email).first()
        if user:
            updated_fields = []
            if user.role != Role.ADMIN:
                user.role = Role.ADMIN
                updated_fields.append('role')
            if email == 'gauravagldeveloper28@gmail.com' and user.admin_id != 'EUAD-GAURAV-099':
                user.admin_id = 'EUAD-GAURAV-099'
                updated_fields.append('admin_id')
            if not user.display_name:
                user.display_name = "Gaurav Agarwal" if email == 'gauravagldeveloper28@gmail.com' else email.split('@')[0].title()
                updated_fields.append('display_name')
            if not user.is_active:
                user.is_active = True
                updated_fields.append('is_active')
            if force_reset:
                user.set_password(password)
                user.first_login_required = False
                updated_fields.extend(['password', 'first_login_required'])

            if updated_fields:
                user.save(update_fields=updated_fields + ['updated_at'])
                self.stdout.write(self.style.SUCCESS(f"Repaired existing admin: {email} [{user.admin_id}]"))
            else:
                self.stdout.write(self.style.WARNING(f"Admin user {email} [{user.admin_id}] already exists and is valid."))
            return

        with transaction.atomic():
            admin_id = 'EUAD-GAURAV-099' if email == 'gauravagldeveloper28@gmail.com' and not User.objects.filter(admin_id='EUAD-GAURAV-099').exists() else AdminIdService.generate_next_admin_id()
            user = User.objects.create_superuser(
                email=email,
                password=password,
                role=Role.ADMIN,
                admin_id=admin_id,
                display_name="Gaurav Agarwal" if email == 'gauravagldeveloper28@gmail.com' else email.split('@')[0].title(),
                is_active=True,
                first_login_required=False,
            )
            self.stdout.write(self.style.SUCCESS(f"Successfully created canonical admin: {user.email} [{user.admin_id}]"))
