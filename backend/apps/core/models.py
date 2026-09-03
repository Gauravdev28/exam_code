import uuid
from django.db import models
from django.core.exceptions import PermissionDenied

class TimeStampedModel(models.Model):
    """
    Abstract base model providing self-updating created_at and updated_at fields.
    """
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']


class UUIDModel(models.Model):
    """
    Abstract base model utilizing a cryptographically secure UUID v4 as primary key.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class ImmutableModel(models.Model):
    """
    Abstract base model enforcing application-level append-only immutability.
    Direct updates and deletions raise PermissionDenied.
    """
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionDenied(
                f"Modification of immutable record {self.__class__.__name__} (ID: {self.pk}) is prohibited."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied(
            f"Deletion of immutable record {self.__class__.__name__} (ID: {self.pk}) is prohibited."
        )
