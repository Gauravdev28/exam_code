from rest_framework.response import Response
from rest_framework import status

class APIResponse(Response):
    """
    Standardized API Response envelope for CODEGUARD.
    Format:
    {
        "status": "success",
        "message": "Optional descriptive message",
        "data": { ... }
    }
    """
    def __init__(self, data=None, message=None, status_code=status.HTTP_200_OK, headers=None, **kwargs):
        payload = {
            "status": "success" if status.is_success(status_code) else "error",
        }
        if message is not None:
            payload["message"] = message
        if data is not None:
            payload["data"] = data

        payload.update(kwargs)
        super().__init__(data=payload, status=status_code, headers=headers)
