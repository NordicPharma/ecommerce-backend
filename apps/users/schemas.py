from ninja import Schema, ModelSchema
from typing import Optional
from datetime import datetime
from django.contrib.auth import get_user_model

User = get_user_model()

class UserRegisterSchema(Schema):
    email: str
    password: str
    first_name: str
    last_name: str
    phone: Optional[str]

class UserLoginSchema(Schema):
    email: str
    password: str

class UserProfileSchema(ModelSchema):
    full_name: str
    
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'first_name', 'last_name', 
                 'phone', 'address', 'city', 'postal_code', 'country',
                 'is_verified', 'date_joined']

class UserUpdateSchema(Schema):
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    city: Optional[str]
    postal_code: Optional[str]
    country: Optional[str]

class ChangePasswordSchema(Schema):
    current_password: str
    new_password: str

class TokenResponseSchema(Schema):
    access: str
    refresh: str
    user: UserProfileSchema