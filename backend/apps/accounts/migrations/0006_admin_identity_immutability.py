# Generated for CODEGUARD Administrator Identity Immutability

from django.db import migrations, models


def designate_primary_admin(apps, schema_editor):
    User = apps.get_model('accounts', 'User')

    # If no administrator accounts exist in the database (e.g. fresh database / test runner),
    # there are no candidates to bootstrap.
    if not User.objects.filter(role='ADMIN').exists():
        return

    # Authoritative pre-existing application state:
    # The canonical Primary Administrator is the superuser administrator.
    candidates = list(User.objects.filter(role='ADMIN', is_superuser=True))

    if len(candidates) == 1:
        primary_admin = candidates[0]
        User.objects.filter(pk=primary_admin.pk).update(primary_admin_marker='PRIMARY')
    elif len(candidates) == 0:
        raise RuntimeError(
            "Migration 0006 Failed: Zero Primary Administrator candidates found (no User with role='ADMIN' and is_superuser=True). "
            "Migration fails closed. REQUIRES BOOTSTRAP VERIFICATION: verify that exactly one superuser administrator account "
            "is provisioned in the target database before running this migration."
        )
    else:
        raise RuntimeError(
            f"Migration 0006 Failed: Multiple Primary Administrator candidates found ({len(candidates)} Users with role='ADMIN' and is_superuser=True). "
            "Migration fails closed. REQUIRES BOOTSTRAP VERIFICATION: resolve ambiguous superuser administrator accounts "
            "so that exactly one canonical superuser exists prior to migration."
        )


def clear_marker(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    User.objects.filter(primary_admin_marker='PRIMARY').update(primary_admin_marker=None)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_admin_identity_hardening'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='primary_admin_marker',
            field=models.CharField(
                blank=True,
                db_index=True,
                default=None,
                help_text="Database-level singleton constraint. Exactly one row in the database may have marker='PRIMARY'; all other rows are NULL.",
                max_length=32,
                null=True,
                unique=True,
                verbose_name='Primary Admin Singleton Marker',
            ),
        ),
        migrations.AddConstraint(
            model_name='user',
            constraint=models.CheckConstraint(
                condition=models.Q(primary_admin_marker__isnull=True) | models.Q(primary_admin_marker='PRIMARY', role='ADMIN'),
                name='primary_admin_marker_valid_state',
            ),
        ),
        migrations.RunPython(designate_primary_admin, reverse_code=clear_marker),
    ]
