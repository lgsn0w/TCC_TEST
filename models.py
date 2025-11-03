from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from pydantic import BaseModel
from .database import Base

class PersonalityUser(Base):
    __tablename__ = "personality_users"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    responses = relationship("PersonalityResponse", back_populates="user")


class PersonalityResponse(Base):
    __tablename__ = "personality_responses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("personality_users.id"))
    question_id = Column(String, index=True)
    answer = Column(Integer)

    user = relationship("PersonalityUser", back_populates="responses")



class ContentResource(Base):
    __tablename__ = "content_resources"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    type = Column(String, nullable=False)
    career_axis = Column(String, index=True, nullable=False)


class ContentResourceResponse(BaseModel):
    id: int
    title: str
    url: str
    type: str
    career_axis: str

    class Config:
        from_attributes = True

