# models.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import secrets

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='operator')  # 'admin' or 'operator'
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    group = db.relationship('Group', back_populates='users')

    @property
    def is_admin(self):
        return self.role == 'admin'

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    users = db.relationship('User', back_populates='group', cascade="all, delete-orphan")
    ssh_hosts = db.relationship('SSHHost', back_populates='group', cascade="all, delete-orphan")
    saved_scripts = db.relationship('SavedScript', back_populates='group', cascade="all, delete-orphan")
    pipelines = db.relationship('Pipeline', back_populates='group', cascade="all, delete-orphan")
    api_tokens = db.relationship('APIToken', back_populates='group', cascade="all, delete-orphan")

class APIToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(100), unique=True, nullable=False, default=lambda: secrets.token_hex(16))
    description = db.Column(db.String(200), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    group = db.relationship('Group', back_populates='api_tokens')

class SSHHost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    friendly_name = db.Column(db.String(100), nullable=False)
    hostname = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(100), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    group = db.relationship('Group', back_populates='ssh_hosts')
    __table_args__ = (db.UniqueConstraint('friendly_name', 'group_id', name='_friendly_name_group_uc'),)

class SavedScript(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    script_type = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    group = db.relationship('Group', back_populates='saved_scripts')
    __table_args__ = (db.UniqueConstraint('name', 'group_id', name='_script_name_group_uc'),)

class Pipeline(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    nodes = db.Column(db.Text, nullable=False)
    edges = db.Column(db.Text, nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    group = db.relationship('Group', back_populates='pipelines')
    __table_args__ = (db.UniqueConstraint('name', 'group_id', name='_pipeline_name_group_uc'),)

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    host_id = db.Column(db.Integer, db.ForeignKey('ssh_host.id'), nullable=False)
    script_id = db.Column(db.Integer, db.ForeignKey('saved_script.id'), nullable=False)
    hour = db.Column(db.Integer, nullable=False)
    minute = db.Column(db.Integer, nullable=False)
    host = db.relationship('SSHHost')
    script = db.relationship('SavedScript')
