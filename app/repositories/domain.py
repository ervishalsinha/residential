from app.models import Complaint, ComplaintComment, EmergencyAlert, Notice, OwnerExpense, Payment, Property, ResidentProfile, Staff, Unit, User, Visitor
from app.repositories.base import BaseRepository

properties_repo = BaseRepository(Property)
residents_repo = BaseRepository(ResidentProfile)
users_repo = BaseRepository(User)
units_repo = BaseRepository(Unit)
complaints_repo = BaseRepository(Complaint)
visitors_repo = BaseRepository(Visitor)
payments_repo = BaseRepository(Payment)
staff_repo = BaseRepository(Staff)
notices_repo = BaseRepository(Notice)
emergency_repo = BaseRepository(EmergencyAlert)
expenses_repo = BaseRepository(OwnerExpense)
complaint_comments_repo = BaseRepository(ComplaintComment)
