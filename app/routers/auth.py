from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.deps import Session
from app.models import User
from app.schemas import Token, UserCreate, UserOut
from app.security import CurrentUser, create_access_token, hash_password, verify_password

router = APIRouter(tags=["auth"])


@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, session: Session) -> User:
    user = User(
        email=data.email.lower(),
        name=data.name,
        phone=data.phone,
        password_hash=hash_password(data.password),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Пользователь с таким email уже есть"
        ) from None
    return user


@router.post("/auth/token", response_model=Token)
async def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], session: Session) -> Token:
    # По стандарту OAuth2 поле называется username, в нём передаём email
    user = await session.scalar(select(User).where(User.email == form.username.lower()))
    if not verify_password(form.password, user.password_hash if user else None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.id))


@router.get("/users/me", response_model=UserOut)
async def me(user: CurrentUser) -> User:
    return user
