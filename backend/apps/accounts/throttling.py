from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

class LoginRateThrottle(AnonRateThrottle):
    """
    Strict rate limiting on login endpoint to mitigate credential brute-force attacks.
    """
    scope = 'login'
    rate = '10/minute'


class BurstRateThrottle(UserRateThrottle):
    """
    Standard user-level burst throttle.
    """
    scope = 'user_burst'
    rate = '60/minute'
