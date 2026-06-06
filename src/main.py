from datetime import date, datetime, timedelta
import hashlib
from pathlib import Path
import secrets

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Date, DateTime, Integer, String, create_engine, text
from sqlalchemy.orm import Mapped, Session, declarative_base, mapped_column, sessionmaker

DATABASE_PATH = Path(__file__).resolve().parent / "bookings.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

PRICE_PER_HOUR = 12
OPENING_HOUR = 8
CLOSING_HOUR = 22
TOTAL_COURTS = 10
PAYMENT_WINDOW_MINUTES = 10
ACCESS_TOKEN_EXPIRE_HOURS = 24

ROLE_ADMIN = "admin"
ROLE_CUSTOMER = "customer"
BOOKING_STATUS_PENDING = "pending_payment"
BOOKING_STATUS_PAID = "paid"
BOOKING_STATUS_CANCELLED_FAILED = "cancelled_payment_failed"
BOOKING_STATUS_CANCELLED_TIMEOUT = "cancelled_payment_timeout"
BOOKING_STATUS_REFUNDED = "refunded"
ACTIVE_BOOKING_STATUSES = {BOOKING_STATUS_PENDING, BOOKING_STATUS_PAID}

PAYMENT_STATUS_PAID = "paid"
PAYMENT_STATUS_FAILED = "failed"
PAYMENT_STATUS_REFUNDED = "refunded"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
auth_scheme = HTTPBearer(auto_error=False)


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    court_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    booking_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    total_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    customer_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=BOOKING_STATUS_PENDING)
    payment_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    refund_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BookingSettings(Base):
    __tablename__ = "booking_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    price_per_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    opening_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    closing_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    total_courts: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=ROLE_CUSTOMER)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SessionToken(Base):
    __tablename__ = "session_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    booking_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_reference: Mapped[str] = mapped_column(String(120), nullable=False)
    card_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


def run_migrations() -> None:
    # Lightweight migration for existing SQLite databases.
    with engine.begin() as connection:
        rows = connection.execute(text("PRAGMA table_info(bookings)")).mappings().all()
        columns = {row["name"] for row in rows}
        migrations = [
            ("customer_id", "ALTER TABLE bookings ADD COLUMN customer_id INTEGER"),
            (
                "status",
                f"ALTER TABLE bookings ADD COLUMN status TEXT NOT NULL DEFAULT '{BOOKING_STATUS_PAID}'",
            ),
            ("payment_due_at", "ALTER TABLE bookings ADD COLUMN payment_due_at DATETIME"),
            ("paid_at", "ALTER TABLE bookings ADD COLUMN paid_at DATETIME"),
            ("cancelled_at", "ALTER TABLE bookings ADD COLUMN cancelled_at DATETIME"),
            ("cancellation_reason", "ALTER TABLE bookings ADD COLUMN cancellation_reason TEXT"),
            ("refund_amount", "ALTER TABLE bookings ADD COLUMN refund_amount INTEGER NOT NULL DEFAULT 0"),
        ]

        for column_name, statement in migrations:
            if column_name not in columns:
                connection.execute(text(statement))


run_migrations()


class BookingBase(BaseModel):
    customer_name: str | None = Field(default=None, min_length=1, max_length=120)
    court_number: int = Field(ge=1)
    booking_date: date
    start_hour: int = Field(ge=0, lt=24)
    duration_hours: int = Field(gt=0)


class BookingCreate(BookingBase):
    pass


class BookingUpdate(BaseModel):
    customer_name: str | None = Field(default=None, min_length=1, max_length=120)
    court_number: int = Field(ge=1)
    booking_date: date
    start_hour: int = Field(ge=0, lt=24)
    duration_hours: int = Field(gt=0)


class BookingResponse(BaseModel):
    id: int
    customer_name: str
    court_number: int
    booking_date: date
    start_hour: int
    duration_hours: int
    end_hour: int
    total_cost: int
    status: str
    payment_due_at: datetime | None
    paid_at: datetime | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    refund_amount: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SettingsResponse(BaseModel):
    price_per_hour: int
    opening_hour: int
    closing_hour: int
    total_courts: int


class SettingsUpdate(BaseModel):
    price_per_hour: int = Field(ge=1)
    opening_hour: int = Field(ge=0, lt=24)
    closing_hour: int = Field(gt=0, le=24)
    total_courts: int = Field(ge=1)


class UserRegister(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: str
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_at: datetime
    user: UserResponse


class PaymentCardInput(BaseModel):
    card_holder_name: str = Field(min_length=1, max_length=120)
    card_number: str = Field(min_length=12, max_length=19)
    exp_month: int = Field(ge=1, le=12)
    exp_year: int = Field(ge=2024, le=2100)
    cvv: str = Field(min_length=3, max_length=4)


class PaymentResult(BaseModel):
    booking_id: int
    status: str
    provider_reference: str
    message: str


class RefundResult(BaseModel):
    booking_id: int
    refund_amount: int
    status: str
    provider_reference: str


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(raw_password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", raw_password.encode("utf-8"), salt.encode("utf-8"), 200000)
    return f"{salt}${digest.hex()}"


def verify_password(raw_password: str, stored_hash: str) -> bool:
    parts = stored_hash.split("$", 1)
    if len(parts) != 2:
        return False
    salt, existing_digest = parts
    check_digest = hashlib.pbkdf2_hmac(
        "sha256", raw_password.encode("utf-8"), salt.encode("utf-8"), 200000
    ).hex()
    return secrets.compare_digest(existing_digest, check_digest)


def sanitize_card_number(card_number: str) -> str:
    return "".join(ch for ch in card_number if ch.isdigit())


def is_valid_luhn(card_number: str) -> bool:
    digits = [int(ch) for ch in card_number if ch.isdigit()]
    if len(digits) < 12:
        return False

    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit

    return checksum % 10 == 0


def ensure_default_admin(db: Session) -> None:
    admin = db.query(User).filter(User.role == ROLE_ADMIN).first()
    if admin is not None:
        return

    seeded = User(
        full_name="System Admin",
        email="admin@bookingsystem.local",
        password_hash=hash_password("Admin123!"),
        role=ROLE_ADMIN,
    )
    db.add(seeded)
    db.commit()


def get_settings(db: Session) -> BookingSettings:
    settings = db.query(BookingSettings).filter(BookingSettings.id == 1).first()
    if settings is None:
        settings = BookingSettings(
            id=1,
            price_per_hour=PRICE_PER_HOUR,
            opening_hour=OPENING_HOUR,
            closing_hour=CLOSING_HOUR,
            total_courts=TOTAL_COURTS,
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def expire_pending_bookings(db: Session) -> None:
    now = datetime.utcnow()
    expired = (
        db.query(Booking)
        .filter(
            Booking.status == BOOKING_STATUS_PENDING,
            Booking.payment_due_at.is_not(None),
            Booking.payment_due_at < now,
        )
        .all()
    )
    if not expired:
        return

    for booking in expired:
        booking.status = BOOKING_STATUS_CANCELLED_TIMEOUT
        booking.cancelled_at = now
        booking.cancellation_reason = "Payment window expired before successful charge."

    db.commit()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization token.")

    token = credentials.credentials
    session = (
        db.query(SessionToken)
        .filter(SessionToken.token == token, SessionToken.expires_at > datetime.utcnow())
        .first()
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.")

    user = db.query(User).filter(User.id == session.user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found for token.")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != ROLE_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access is required.")
    return current_user


def validate_settings_values(settings: SettingsUpdate) -> None:
    if settings.opening_hour >= settings.closing_hour:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="opening_hour must be less than closing_hour.",
        )


def validate_booking_window(start_hour: int, duration_hours: int, opening_hour: int, closing_hour: int) -> int:
    if start_hour < opening_hour or start_hour >= closing_hour:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"start_hour must be between {opening_hour} and {closing_hour - 1}.",
        )

    end_hour = start_hour + duration_hours
    if end_hour > closing_hour:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Booking must end by {closing_hour}:00.",
        )
    return end_hour


def validate_court_number(court_number: int, total_courts: int) -> None:
    if court_number < 1 or court_number > total_courts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"court_number must be between 1 and {total_courts}.",
        )


def parse_date_query(raw_date: str) -> date:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw_date, fmt).date()
        except ValueError:
            continue

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="booking_date must be in YYYY-MM-DD or YYYY/MM/DD format.",
    )


def simulate_payment_gateway(card: PaymentCardInput, amount: int) -> tuple[bool, str, str | None]:
    if amount <= 0:
        return False, "invalid_amount", "Amount must be positive."

    normalized_number = sanitize_card_number(card.card_number)
    if not is_valid_luhn(normalized_number):
        return False, "invalid_card", "Card number failed validation."

    now = datetime.utcnow()
    if card.exp_year < now.year or (card.exp_year == now.year and card.exp_month < now.month):
        return False, "expired_card", "Card is expired."

    if not card.cvv.isdigit() or len(card.cvv) not in (3, 4):
        return False, "invalid_cvv", "CVV must be 3 or 4 digits."

    # Deterministic gateway failure case for testing error handling.
    if normalized_number.endswith("0000"):
        return False, "gateway_declined", "Payment gateway declined the card."

    return True, f"PG-{secrets.token_hex(6).upper()}", None


def has_conflict(
    db: Session,
    *,
    booking_date: date,
    court_number: int,
    start_hour: int,
    duration_hours: int,
    exclude_booking_id: int | None = None,
) -> bool:
    new_end = start_hour + duration_hours
    existing_bookings = (
        db.query(Booking)
        .filter(
            Booking.booking_date == booking_date,
            Booking.court_number == court_number,
            Booking.status.in_(ACTIVE_BOOKING_STATUSES),
        )
        .all()
    )

    for existing in existing_bookings:
        if exclude_booking_id is not None and existing.id == exclude_booking_id:
            continue

        existing_start = existing.start_hour
        existing_end = existing.start_hour + existing.duration_hours
        if start_hour < existing_end and existing_start < new_end:
            return True

    return False


def to_response(booking: Booking) -> BookingResponse:
    return BookingResponse(
        id=booking.id,
        customer_name=booking.customer_name,
        court_number=booking.court_number,
        booking_date=booking.booking_date,
        start_hour=booking.start_hour,
        duration_hours=booking.duration_hours,
        end_hour=booking.start_hour + booking.duration_hours,
        total_cost=booking.total_cost,
        status=booking.status,
        payment_due_at=booking.payment_due_at,
        paid_at=booking.paid_at,
        cancelled_at=booking.cancelled_at,
        cancellation_reason=booking.cancellation_reason,
        refund_amount=booking.refund_amount,
        created_at=booking.created_at,
    )


app = FastAPI(title="Badminton Court Booking API", version="1.0.0")

# Allow Node.js frontend apps to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root(db: Session = Depends(get_db)):
    ensure_default_admin(db)
    settings = get_settings(db)
    return {
        "message": "Badminton booking server is running.",
        "price_per_hour": settings.price_per_hour,
        "opening_hour": settings.opening_hour,
        "closing_hour": settings.closing_hour,
        "total_courts": settings.total_courts,
        "payment_window_minutes": PAYMENT_WINDOW_MINUTES,
    }


@app.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email.strip().lower()).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered.")

    user = User(
        full_name=payload.full_name.strip(),
        email=payload.email.strip().lower(),
        password_hash=hash_password(payload.password),
        role=ROLE_CUSTOMER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/auth/login", response_model=AuthTokenResponse)
def login_user(payload: UserLogin, db: Session = Depends(get_db)):
    ensure_default_admin(db)
    user = db.query(User).filter(User.email == payload.email.strip().lower()).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    token = secrets.token_urlsafe(48)
    expires_at = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)

    db.query(SessionToken).filter(SessionToken.user_id == user.id).delete()
    db.add(SessionToken(user_id=user.id, token=token, expires_at=expires_at))
    db.commit()

    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        expires_at=expires_at,
        user=user,
    )


@app.get("/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@app.get("/admin/settings", response_model=SettingsResponse)
def read_settings(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    settings = get_settings(db)
    return SettingsResponse(
        price_per_hour=settings.price_per_hour,
        opening_hour=settings.opening_hour,
        closing_hour=settings.closing_hour,
        total_courts=settings.total_courts,
    )


@app.put("/admin/settings", response_model=SettingsResponse)
def update_settings(payload: SettingsUpdate, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    validate_settings_values(payload)
    settings = get_settings(db)

    settings.price_per_hour = payload.price_per_hour
    settings.opening_hour = payload.opening_hour
    settings.closing_hour = payload.closing_hour
    settings.total_courts = payload.total_courts

    db.commit()
    db.refresh(settings)

    return SettingsResponse(
        price_per_hour=settings.price_per_hour,
        opening_hour=settings.opening_hour,
        closing_hour=settings.closing_hour,
        total_courts=settings.total_courts,
    )


@app.get("/admin/customers", response_model=list[UserResponse])
def list_customers(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(User).order_by(User.created_at.desc()).all()


@app.post("/bookings", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def create_booking(
    payload: BookingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expire_pending_bookings(db)
    settings = get_settings(db)
    customer_name = payload.customer_name.strip() if payload.customer_name else current_user.full_name

    validate_court_number(payload.court_number, settings.total_courts)
    validate_booking_window(
        payload.start_hour,
        payload.duration_hours,
        settings.opening_hour,
        settings.closing_hour,
    )

    if has_conflict(
        db,
        booking_date=payload.booking_date,
        court_number=payload.court_number,
        start_hour=payload.start_hour,
        duration_hours=payload.duration_hours,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Selected court and time slot is already booked.",
        )

    booking = Booking(
        customer_id=current_user.id,
        customer_name=customer_name,
        court_number=payload.court_number,
        booking_date=payload.booking_date,
        start_hour=payload.start_hour,
        duration_hours=payload.duration_hours,
        total_cost=payload.duration_hours * settings.price_per_hour,
        status=BOOKING_STATUS_PENDING,
        payment_due_at=datetime.utcnow() + timedelta(minutes=PAYMENT_WINDOW_MINUTES),
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return to_response(booking)


@app.get("/bookings", response_model=list[BookingResponse])
def list_bookings(
    booking_date: str | None = Query(default=None),
    court_number: int | None = Query(default=None, ge=1),
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expire_pending_bookings(db)
    settings = get_settings(db)
    query = db.query(Booking)

    if current_user.role != ROLE_ADMIN:
        query = query.filter(Booking.customer_id == current_user.id)

    if booking_date is not None:
        parsed_booking_date = parse_date_query(booking_date)
        query = query.filter(Booking.booking_date == parsed_booking_date)
    if court_number is not None:
        validate_court_number(court_number, settings.total_courts)
        query = query.filter(Booking.court_number == court_number)
    if status_filter is not None:
        query = query.filter(Booking.status == status_filter)

    bookings = query.order_by(Booking.booking_date, Booking.court_number, Booking.start_hour).all()
    return [to_response(item) for item in bookings]


@app.get("/bookings/{booking_id}", response_model=BookingResponse)
def get_booking(booking_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    expire_pending_bookings(db)
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")

    if current_user.role != ROLE_ADMIN and booking.customer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this booking.")

    return to_response(booking)


@app.put("/bookings/{booking_id}", response_model=BookingResponse)
def update_booking(
    booking_id: int,
    payload: BookingUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expire_pending_bookings(db)
    settings = get_settings(db)
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")

    if current_user.role != ROLE_ADMIN and booking.customer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this booking.")

    if booking.status != BOOKING_STATUS_PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending-payment bookings can be edited.",
        )

    validate_court_number(payload.court_number, settings.total_courts)
    validate_booking_window(
        payload.start_hour,
        payload.duration_hours,
        settings.opening_hour,
        settings.closing_hour,
    )
    if has_conflict(
        db,
        booking_date=payload.booking_date,
        court_number=payload.court_number,
        start_hour=payload.start_hour,
        duration_hours=payload.duration_hours,
        exclude_booking_id=booking_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Selected court and time slot is already booked.",
        )

    booking.customer_name = payload.customer_name.strip() if payload.customer_name else current_user.full_name
    booking.court_number = payload.court_number
    booking.booking_date = payload.booking_date
    booking.start_hour = payload.start_hour
    booking.duration_hours = payload.duration_hours
    booking.total_cost = payload.duration_hours * settings.price_per_hour
    booking.payment_due_at = datetime.utcnow() + timedelta(minutes=PAYMENT_WINDOW_MINUTES)

    db.commit()
    db.refresh(booking)
    return to_response(booking)


@app.post("/bookings/{booking_id}/pay", response_model=PaymentResult)
def pay_booking(
    booking_id: int,
    card: PaymentCardInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expire_pending_bookings(db)
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")

    if current_user.role != ROLE_ADMIN and booking.customer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this booking.")

    if booking.status != BOOKING_STATUS_PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking is not in pending payment state.",
        )

    now = datetime.utcnow()
    if booking.payment_due_at is not None and booking.payment_due_at < now:
        booking.status = BOOKING_STATUS_CANCELLED_TIMEOUT
        booking.cancelled_at = now
        booking.cancellation_reason = "Payment window expired before successful charge."
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment window expired.")

    success, provider_ref, failure_reason = simulate_payment_gateway(card, booking.total_cost)
    card_last4 = sanitize_card_number(card.card_number)[-4:]

    if not success:
        booking.status = BOOKING_STATUS_CANCELLED_FAILED
        booking.cancelled_at = now
        booking.cancellation_reason = failure_reason
        db.add(
            PaymentTransaction(
                booking_id=booking.id,
                amount=booking.total_cost,
                status=PAYMENT_STATUS_FAILED,
                provider_reference=provider_ref,
                card_last4=card_last4,
                failure_reason=failure_reason,
            )
        )
        db.commit()
        return PaymentResult(
            booking_id=booking.id,
            status=BOOKING_STATUS_CANCELLED_FAILED,
            provider_reference=provider_ref,
            message=failure_reason or "Payment failed",
        )

    booking.status = BOOKING_STATUS_PAID
    booking.paid_at = now
    booking.cancellation_reason = None
    db.add(
        PaymentTransaction(
            booking_id=booking.id,
            amount=booking.total_cost,
            status=PAYMENT_STATUS_PAID,
            provider_reference=provider_ref,
            card_last4=card_last4,
        )
    )
    db.commit()

    return PaymentResult(
        booking_id=booking.id,
        status=BOOKING_STATUS_PAID,
        provider_reference=provider_ref,
        message="Payment successful.",
    )


@app.post("/bookings/{booking_id}/refund", response_model=RefundResult)
def refund_booking(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")

    if current_user.role != ROLE_ADMIN and booking.customer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this booking.")

    if booking.status != BOOKING_STATUS_PAID:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only paid bookings can be refunded.")

    provider_ref = f"RF-{secrets.token_hex(6).upper()}"
    booking.status = BOOKING_STATUS_REFUNDED
    booking.refund_amount = booking.total_cost
    booking.cancelled_at = datetime.utcnow()
    booking.cancellation_reason = "Refunded to credit card."

    db.add(
        PaymentTransaction(
            booking_id=booking.id,
            amount=booking.total_cost,
            status=PAYMENT_STATUS_REFUNDED,
            provider_reference=provider_ref,
        )
    )
    db.commit()

    return RefundResult(
        booking_id=booking.id,
        refund_amount=booking.total_cost,
        status=BOOKING_STATUS_REFUNDED,
        provider_reference=provider_ref,
    )


@app.delete("/bookings/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_booking(booking_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")

    if current_user.role != ROLE_ADMIN and booking.customer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this booking.")

    db.delete(booking)
    db.commit()
