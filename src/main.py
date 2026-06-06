from datetime import date, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Date, DateTime, Integer, String, create_engine
from sqlalchemy.orm import Mapped, Session, declarative_base, mapped_column, sessionmaker

DATABASE_PATH = Path(__file__).resolve().parent / "bookings.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

PRICE_PER_HOUR = 12
OPENING_HOUR = 8
CLOSING_HOUR = 22
TOTAL_COURTS = 10

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    court_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    booking_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    total_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BookingSettings(Base):
    __tablename__ = "booking_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    price_per_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    opening_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    closing_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    total_courts: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


Base.metadata.create_all(bind=engine)


class BookingBase(BaseModel):
    customer_name: str = Field(min_length=1, max_length=120)
    court_number: int = Field(ge=1)
    booking_date: date
    start_hour: int = Field(ge=0, lt=24)
    duration_hours: int = Field(gt=0)


class BookingCreate(BookingBase):
    pass


class BookingUpdate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=120)
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


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
        .filter(Booking.booking_date == booking_date, Booking.court_number == court_number)
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
    settings = get_settings(db)
    return {
        "message": "Badminton booking server is running.",
        "price_per_hour": settings.price_per_hour,
        "opening_hour": settings.opening_hour,
        "closing_hour": settings.closing_hour,
        "total_courts": settings.total_courts,
    }


@app.get("/admin/settings", response_model=SettingsResponse)
def read_settings(db: Session = Depends(get_db)):
    settings = get_settings(db)
    return SettingsResponse(
        price_per_hour=settings.price_per_hour,
        opening_hour=settings.opening_hour,
        closing_hour=settings.closing_hour,
        total_courts=settings.total_courts,
    )


@app.put("/admin/settings", response_model=SettingsResponse)
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)):
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


@app.post("/bookings", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def create_booking(payload: BookingCreate, db: Session = Depends(get_db)):
    settings = get_settings(db)
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
        customer_name=payload.customer_name.strip(),
        court_number=payload.court_number,
        booking_date=payload.booking_date,
        start_hour=payload.start_hour,
        duration_hours=payload.duration_hours,
        total_cost=payload.duration_hours * settings.price_per_hour,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return to_response(booking)


@app.get("/bookings", response_model=list[BookingResponse])
def list_bookings(
    booking_date: str | None = Query(default=None),
    court_number: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
):
    settings = get_settings(db)
    query = db.query(Booking)

    if booking_date is not None:
        parsed_booking_date = parse_date_query(booking_date)
        query = query.filter(Booking.booking_date == parsed_booking_date)
    if court_number is not None:
        validate_court_number(court_number, settings.total_courts)
        query = query.filter(Booking.court_number == court_number)

    bookings = query.order_by(Booking.booking_date, Booking.court_number, Booking.start_hour).all()
    return [to_response(item) for item in bookings]


@app.get("/bookings/{booking_id}", response_model=BookingResponse)
def get_booking(booking_id: int, db: Session = Depends(get_db)):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")
    return to_response(booking)


@app.put("/bookings/{booking_id}", response_model=BookingResponse)
def update_booking(booking_id: int, payload: BookingUpdate, db: Session = Depends(get_db)):
    settings = get_settings(db)
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")

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

    booking.customer_name = payload.customer_name.strip()
    booking.court_number = payload.court_number
    booking.booking_date = payload.booking_date
    booking.start_hour = payload.start_hour
    booking.duration_hours = payload.duration_hours
    booking.total_cost = payload.duration_hours * settings.price_per_hour

    db.commit()
    db.refresh(booking)
    return to_response(booking)


@app.delete("/bookings/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_booking(booking_id: int, db: Session = Depends(get_db)):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")

    db.delete(booking)
    db.commit()
