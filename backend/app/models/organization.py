"""Organization identity, commercial entitlements and append-only audit records."""
from datetime import datetime

from flask import current_app, has_app_context, has_request_context
from sqlalchemy.orm import declared_attr

from app import db


def _request_organization_id(context=None):
    # Delayed import avoids a model/policy import cycle. Offline jobs must pass ID.
    from app.services.organization_context import require_organization_id
    # Legacy/unit-test fixtures intentionally create users inside an app context
    # before a request exists. This escape hatch is disabled by default and is
    # enabled only by TestingConfig; production workers must pass an org ID.
    if has_request_context():
        return require_organization_id()
    if has_app_context() and current_app.config.get('ALLOW_IMPLICIT_ORGANIZATION'):
        # Use the INSERT connection supplied by SQLAlchemy's default context;
        # opening a nested ORM flush here would recurse. This compatibility path
        # is only for legacy test/local fixtures and never runs in production.
        connection = getattr(context, 'connection', None)
        if connection is not None:
            organization_id = connection.execute(
                db.select(Organization.__table__.c.id).where(
                    Organization.__table__.c.code == 'default')
            ).scalar_one_or_none()
            if organization_id is None:
                connection.execute(Organization.__table__.insert().values(
                    code='default', name='默认测试机构', status='active',
                    user_limit=500, storage_limit_bytes=1073741824,
                    ai_monthly_token_limit=100000, concurrent_task_limit=2,
                    ai_enabled=False, created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()))
                organization_id = connection.execute(
                    db.select(Organization.__table__.c.id).where(
                        Organization.__table__.c.code == 'default')
                ).scalar_one()
            return organization_id
        organization = db.session.query(Organization).filter_by(code='default').first()
        if organization is not None:
            return organization.id
    return require_organization_id()


class OrganizationOwned:
    @declared_attr
    def organization_id(cls):
        return db.Column(db.Integer, db.ForeignKey('organizations.id'),
                         nullable=False, index=True, default=_request_organization_id)


class Organization(db.Model):
    __tablename__ = 'organizations'
    __table_args__ = (
        db.CheckConstraint("status IN ('active', 'disabled')", name='ck_organization_status'),
        db.CheckConstraint('user_limit >= 0 AND storage_limit_bytes >= 0 AND '
                           'ai_monthly_token_limit >= 0 AND concurrent_task_limit >= 0',
                           name='ck_organization_limits'),
    )

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='active')
    expires_at = db.Column(db.DateTime)
    user_limit = db.Column(db.Integer, nullable=False, default=500)
    storage_limit_bytes = db.Column(db.BigInteger, nullable=False, default=1073741824)
    ai_monthly_token_limit = db.Column(db.BigInteger, nullable=False, default=100000)
    concurrent_task_limit = db.Column(db.Integer, nullable=False, default=2)
    ai_enabled = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    def to_dict(self):
        data = {key: getattr(self, key) for key in (
            'id', 'code', 'name', 'status', 'user_limit', 'storage_limit_bytes',
            'ai_monthly_token_limit', 'concurrent_task_limit', 'ai_enabled')}
        data.update({key: getattr(self, key).isoformat() if getattr(self, key) else None
                     for key in ('expires_at', 'created_at', 'updated_at')})
        data['is_expired'] = bool(self.expires_at and self.expires_at <= datetime.utcnow())
        data['read_only'] = data['is_expired'] and self.status == 'active'
        return data


class OrganizationClass(OrganizationOwned, db.Model):
    __tablename__ = 'organization_classes'
    __table_args__ = (db.UniqueConstraint('organization_id', 'name',
                                        name='uq_organization_class_name'),)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'organization_id': self.organization_id, 'name': self.name,
                'created_at': self.created_at.isoformat() if self.created_at else None}


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    __table_args__ = (db.Index('ix_audit_organization_created', 'organization_id', 'created_at'),)

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'))
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(80))
    target_id = db.Column(db.String(100))
    details = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'organization_id': self.organization_id,
                'actor_id': self.actor_id, 'action': self.action,
                'target_type': self.target_type, 'target_id': self.target_id,
                'details': self.details,
                'created_at': self.created_at.isoformat() if self.created_at else None}
