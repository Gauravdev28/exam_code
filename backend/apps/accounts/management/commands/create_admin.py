import os
from django.core.management.base import BaseCommand
from apps.accounts.models import User, Role

class Command(BaseCommand):
    help = 'Creates default administrator account for development if not present.'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, default='admin@codeguard.local')
        parser.add_argument('--password', type=str, default='Admin@CodeGuard2026!')

    def handle(self, *args, **options):
        email = options['email'].lower()
        password = options['password']

        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING(f"Admin user {email} already exists."))
            return

        user = User.objects.create_superuser(
            email=email,
            password=password,
            role=Role.ADMIN
        )
        self.stdout.write(self.style.SUCCESS(f"Successfully created admin user: {user.email}"))
