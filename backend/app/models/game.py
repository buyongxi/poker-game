from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class GameRecord(Base):
    __tablename__ = "game_records"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    winners = Column(JSON, nullable=False)  # [{"user_id": 1, "amount": 100}]
    pot_amount = Column(Integer, nullable=False)
    community_cards = Column(String(20), nullable=False)  # e.g. "AhKsQdJc2h"
    game_data = Column(JSON, nullable=True)  # Full game state for replay
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    room = relationship("Room", back_populates="game_records")
