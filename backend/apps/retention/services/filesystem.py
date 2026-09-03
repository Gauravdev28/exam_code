import os
from django.conf import settings
from django.utils import timezone
import logging

from apps.retention.models import (
    FileCleanupQueue,
    FileCleanupStatus,
)
from .tombstone import TombstoneService

logger = logging.getLogger('codeguard.retention')


class FilesystemCleanupWorker:
    @classmethod
    def is_safe_path(cls, file_path):
        """
        Validates that the file path is safe and strictly contained within MEDIA_ROOT.
        Protects against path traversal attacks (e.g. ../../etc/passwd).
        """
        if not file_path:
            return False
        
        # Check for path traversal elements
        if '..' in file_path:
            return False

        try:
            abs_path = os.path.abspath(file_path)
            media_root_abs = os.path.abspath(settings.MEDIA_ROOT)
            # Must start with media root
            return abs_path.startswith(media_root_abs)
        except Exception:
            return False

    @classmethod
    def process_attempt_cleanups(cls, attempt_id, operator_user=None):
        """
        Processes pending file unlinks for an attempt.
        Idempotent and retryable.
        """
        queue_items = FileCleanupQueue.objects.filter(
            attempt_id=attempt_id,
            status__in=[FileCleanupStatus.PENDING, FileCleanupStatus.RETRYING]
        )

        confirmed_count = 0
        retrying_count = 0
        failed_count = 0

        for item in queue_items:
            path = item.file_path

            # Path traversal check
            if not cls.is_safe_path(path):
                item.status = FileCleanupStatus.FAILED
                item.last_error = f"Path traversal attempt or path outside MEDIA_ROOT: {path}"
                item.save(update_fields=['status', 'last_error', 'updated_at'])
                failed_count += 1
                continue

            try:
                if os.path.exists(path):
                    os.remove(path)
                item.status = FileCleanupStatus.CONFIRMED
                item.confirmed_deleted_at = timezone.now()
                item.save(update_fields=['status', 'confirmed_deleted_at', 'updated_at'])
                confirmed_count += 1
            except FileNotFoundError:
                # Already gone, treat as confirmed
                item.status = FileCleanupStatus.CONFIRMED
                item.confirmed_deleted_at = timezone.now()
                item.save(update_fields=['status', 'confirmed_deleted_at', 'updated_at'])
                confirmed_count += 1
            except OSError as exc:
                logger.warning(f"Failed to unlink file {path} for attempt {attempt_id}: {exc}")
                item.retry_count += 1
                item.last_error = str(exc)
                item.status = FileCleanupStatus.RETRYING
                item.save(update_fields=['retry_count', 'last_error', 'status', 'updated_at'])
                retrying_count += 1

        # Check if 100% of files for this attempt are confirmed deleted
        unconfirmed = FileCleanupQueue.objects.filter(attempt_id=attempt_id).exclude(
            status=FileCleanupStatus.CONFIRMED
        )
        if not unconfirmed.exists():
            # 100% of required physical cleanups confirmed! Mint permanent tombstone
            TombstoneService.mint_tombstone(attempt_id, operator_user=operator_user)

        return {
            'confirmed': confirmed_count,
            'retrying': retrying_count,
            'failed': failed_count,
        }
