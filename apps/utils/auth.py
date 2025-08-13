from ninja.security import HttpBearer
from ninja_jwt.authentication import JWTAuth as BaseJWTAuth
from ninja_jwt.tokens import AccessToken
from django.contrib.auth import get_user_model

User = get_user_model()

class JWTAuth(BaseJWTAuth):
    """Autenticación JWT personalizada para Django Ninja"""
    
    def authenticate(self, request, token):
        try:
            validated_token = AccessToken(token)
            user = User.objects.get(id=validated_token['user_id'])
            return user
        except Exception:
            return None