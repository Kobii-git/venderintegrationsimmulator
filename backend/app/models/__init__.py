import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base
from app.domain.enums import (
    EventInstanceStatus,
    FidelityMode,
    PayloadSource,
    SimulationStatus,
)


class Simulation(Base):
    __tablename__ = "simulations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scenario_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scenario_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    simulation_mode: Mapped[str] = mapped_column(String(64), nullable=False, default="push_webhook")
    fidelity_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default=FidelityMode.VENDOR_ACCURATE
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=SimulationStatus.STOPPED, index=True
    )
    random_seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    runtime_state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    devices: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    replay_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    targets: Mapped[list["SimulationTarget"]] = relationship(
        cascade="all, delete-orphan", order_by="SimulationTarget.position"
    )
    destination: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    auth_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    scenario_overrides: Mapped[dict[str, dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    schedule: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    fault_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    inbound_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    configuration_version: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    destination_secret_values: Mapped[dict[str, str]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    event_instances: Mapped[list["EventInstance"]] = relationship(
        back_populates="simulation",
        cascade="all, delete-orphan",
    )
    inbound_request_logs: Mapped[list["InboundRequestLog"]] = relationship(
        back_populates="simulation",
        cascade="all, delete-orphan",
    )
    oauth_access_tokens: Mapped[list["OAuthAccessToken"]] = relationship(
        back_populates="simulation",
        cascade="all, delete-orphan",
    )
    pull_dataset_activations: Mapped[list["PullDatasetActivation"]] = relationship(
        back_populates="simulation",
        cascade="all, delete-orphan",
    )


class EventInstance(Base):
    __tablename__ = "event_instances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    simulation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scenario_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="scenario")
    action_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    fidelity_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=EventInstanceStatus.PENDING, index=True
    )
    payload_source: Mapped[str] = mapped_column(
        String(32), nullable=False, default=PayloadSource.GENERATED, index=True
    )
    replayed_from_event_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    simulator_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    simulation: Mapped["Simulation"] = relationship(back_populates="event_instances")
    delivery_attempts: Mapped[list["DeliveryAttempt"]] = relationship(
        back_populates="event_instance",
        cascade="all, delete-orphan",
        order_by=lambda: (
            DeliveryAttempt.attempt_number,
            DeliveryAttempt.started_at,
            DeliveryAttempt.id,
        ),
    )


class DeliveryAttempt(Base):
    __tablename__ = "delivery_attempts"
    __table_args__ = (
        Index(
            "ix_delivery_attempts_event_order",
            "event_instance_id",
            "attempt_number",
            "started_at",
            "id",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_instance_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("event_instances.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    delivery_confirmation: Mapped[str | None] = mapped_column(String(32), nullable=True)
    delivery_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    transport_id: Mapped[str] = mapped_column(String(64), nullable=False)
    destination_summary: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    request_url_redacted: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    request_method: Mapped[str | None] = mapped_column(String(16), nullable=True)
    request_headers_redacted: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    request_query_params_redacted: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    request_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_headers_redacted: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(nullable=False, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(32), nullable=True, default=None)

    event_instance: Mapped["EventInstance"] = relationship(back_populates="delivery_attempts")


class InboundRequestLog(Base):
    __tablename__ = "inbound_request_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    simulation_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("simulations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    product_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    route_id: Mapped[str] = mapped_column(String(64), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    request_method: Mapped[str] = mapped_column(String(16), nullable=False)
    request_path: Mapped[str] = mapped_column(String(512), nullable=False)
    request_query_params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    request_headers_redacted: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    request_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_status_code: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    response_headers: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_method_id: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    auth_result: Mapped[str] = mapped_column(String(32), nullable=False, default="skipped")
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_returned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="api", index=True)
    token_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    simulation: Mapped["Simulation"] = relationship(back_populates="inbound_request_logs")


class OAuthAccessToken(Base):
    __tablename__ = "oauth_access_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    simulation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("simulations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    client_id: Mapped[str] = mapped_column(String(255), nullable=False)
    scope: Mapped[str | None] = mapped_column(String(512), nullable=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    revoked: Mapped[bool] = mapped_column(nullable=False, default=False)

    simulation: Mapped["Simulation"] = relationship(back_populates="oauth_access_tokens")


class PullDatasetActivation(Base):
    __tablename__ = "pull_dataset_activations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    simulation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("simulations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    simulation: Mapped["Simulation"] = relationship(back_populates="pull_dataset_activations")
    items: Mapped[list["PullDatasetItem"]] = relationship(
        back_populates="activation",
        cascade="all, delete-orphan",
    )


class PullDatasetItem(Base):
    __tablename__ = "pull_dataset_items"
    __table_args__ = (
        UniqueConstraint(
            "activation_id", "route_id", "sequence", name="uq_pull_dataset_route_sequence"
        ),
        Index(
            "ix_pull_dataset_items_route_time",
            "activation_id",
            "route_id",
            "generated_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    activation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("pull_dataset_activations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    simulation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("simulations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    route_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scenario_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    activation: Mapped["PullDatasetActivation"] = relationship(back_populates="items")


class SimulationTarget(Base):
    __tablename__ = "simulation_targets"
    __table_args__ = (UniqueConstraint("simulation_id", "target_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    simulation_id: Mapped[str] = mapped_column(
        ForeignKey("simulations.id", ondelete="CASCADE"), index=True
    )
    target_id: Mapped[str] = mapped_column(String(64))
    position: Mapped[int] = mapped_column(Integer, default=0)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    stats: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class DeliveryJob(Base):
    __tablename__ = "delivery_jobs"
    __table_args__ = (Index("ix_jobs_target_status", "target_key", "status", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    simulation_id: Mapped[str] = mapped_column(
        ForeignKey("simulations.id", ondelete="CASCADE"), index=True
    )
    event_id: Mapped[str] = mapped_column(
        ForeignKey("event_instances.id", ondelete="CASCADE"), index=True
    )
    target_key: Mapped[str] = mapped_column(String(128))
    target_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UploadedDataset(Base):
    __tablename__ = "uploaded_datasets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    format: Mapped[str] = mapped_column(String(16))
    filename: Mapped[str] = mapped_column(String(64), unique=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    record_count: Mapped[int] = mapped_column(Integer)
    timestamp_fields: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
