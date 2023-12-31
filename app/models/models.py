from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, Date, Time
from sqlalchemy.orm import relationship, backref
from app.database import Base
from flask_login import UserMixin

class Roles(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True)
    role = Column(String(255), nullable=False)

class Users(Base, UserMixin):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    surname = Column(String(255), nullable=False)
    username = Column(String(255), nullable=False, unique=True)
    hash = Column(String(255), nullable=False)
    role_id = Column(Integer, ForeignKey('roles.id'))
    role = relationship('Roles', backref=backref('users', lazy=True))

class Groups(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)

class Events(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(String(255), nullable=True) 
    date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False) 
    end_time = Column(Time, nullable=False)
    n_assistants = Column(Integer, nullable=False) # max asistants to event
    color = Column(String(7), nullable=True) # Hexadecimal color code
    group_id = Column(Integer, ForeignKey('groups.id', ondelete='CASCADE'))
    group = relationship('Groups', backref=backref('events', lazy=True))

# Many to many relation table
class UserEvents(Base):
    __tablename__ = "userevents"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'))
    event_id = Column(Integer, ForeignKey('events.id', ondelete='CASCADE'))
    user = relationship('Users', backref=backref('userevents', lazy=True))
    event = relationship('Events', backref=backref('userevents', lazy=True))

# Many to many relation table
class UserGroups(Base):
    __tablename__ = "usergroups"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'))
    group_id = Column(Integer, ForeignKey('groups.id', ondelete='CASCADE'))
    user = relationship('Users', backref=backref('usergroups', lazy=True))
    event = relationship('Groups', backref=backref('usergroups', lazy=True))
