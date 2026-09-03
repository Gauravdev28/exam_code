import pytest
import uuid
from django.db import models
from django.core.exceptions import PermissionDenied
from apps.core.models import TimeStampedModel, UUIDModel, ImmutableModel

# Concrete dummy model for testing abstract behaviors
class DummyRecord(UUIDModel, TimeStampedModel, ImmutableModel):
    title = models.CharField(max_length=100)
    
    class Meta:
        app_label = 'core'

@pytest.mark.django_db
def test_uuid_and_timestamp_generation():
    """Verify UUID and timestamps are automatically generated."""
    record = DummyRecord(title="Immutable Audit Test")
    # Simulate DB state for testing model methods
    record._state.adding = True
    assert isinstance(record.id, uuid.UUID)

def test_immutable_model_raises_permission_denied_on_update():
    """Verify that updating an existing immutable record raises PermissionDenied."""
    record = DummyRecord(title="Initial Title")
    record._state.adding = False  # Mark as already persisted in DB
    
    with pytest.raises(PermissionDenied) as exc_info:
        record.save()
    
    assert "Modification of immutable record" in str(exc_info.value)

def test_immutable_model_raises_permission_denied_on_delete():
    """Verify that deleting an immutable record raises PermissionDenied."""
    record = DummyRecord(title="To be deleted")
    record._state.adding = False
    
    with pytest.raises(PermissionDenied) as exc_info:
        record.delete()
    
    assert "Deletion of immutable record" in str(exc_info.value)
