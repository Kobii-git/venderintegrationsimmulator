"""Durable target workers. Network waits occur outside database write transactions.
One task per simulation target with bounded in-flight batches. Restart is at-least-once.
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import get_session_factory
from app.formats.azure_ingestion import AZURE_TRANSPORTS, ingestion_record
from app.models import DeliveryJob, EventInstance, Simulation
from app.services.destination_config import destination_for_delivery
from app.services.simulation_runtime import SimulationRuntimeService
from app.transports.delivery_result import DeliveryResult

logger = logging.getLogger(__name__)


class DeliveryQueue:
    def __init__(self, products: Any, transport: Any, encryptor: Any) -> None:
        self.products, self.transport, self.encryptor = products, transport, encryptor
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._monitor: asyncio.Task[None] | None = None
        self._stopping = False

    def start(self) -> None:
        with get_session_factory()() as db:
            db.query(DeliveryJob).filter_by(status="active").update({"status": "pending"})
            db.commit()
        self._monitor = asyncio.create_task(self._discover())

    async def close(self) -> None:
        self._stopping = True
        if self._monitor:
            self._monitor.cancel()
            await asyncio.gather(self._monitor, return_exceptions=True)
        tasks = list(self._tasks.values())
        if tasks:
            done, pending = await asyncio.wait(tasks, timeout=10)
            for task in pending:
                task.cancel()
            await asyncio.gather(*done, *pending, return_exceptions=True)
        with get_session_factory()() as db:
            db.query(DeliveryJob).filter_by(status="active").update({"status": "pending"})
            db.commit()

    async def _discover(self) -> None:
        while not self._stopping:
            with get_session_factory()() as db:
                keys = [
                    r[0]
                    for r in db.query(DeliveryJob.target_key).filter_by(status="pending").distinct()
                ]
            for key in keys:
                if key not in self._tasks or self._tasks[key].done():
                    self._tasks[key] = asyncio.create_task(self._worker(key))
            self._tasks = {k: t for k, t in self._tasks.items() if not t.done()}
            await asyncio.sleep(0.05)

    async def _worker(self, key: str) -> None:
        while not self._stopping:
            try:
                with get_session_factory()() as db:
                    jobs = (
                        db.query(DeliveryJob)
                        .filter_by(target_key=key, status="pending")
                        .order_by(DeliveryJob.created_at, DeliveryJob.id)
                        .limit(20)
                        .all()
                    )
                    if not jobs:
                        return
                    ids = [j.id for j in jobs]
                    configs = {j.id: dict(j.config) for j in jobs}
                    event_ids = {j.id: j.event_id for j in jobs}
                    simulation_id = jobs[0].simulation_id
                    for job in jobs:
                        job.status = "active"
                    db.commit()
                # Read session only during network operations; attempts collected in memory.
                with get_session_factory()() as db:
                    runtime = SimulationRuntimeService(
                        db, self.products, self.transport, self.encryptor
                    )
                    runtime._attempt_buffer = []
                    simulation = db.get(Simulation, simulation_id)
                    if simulation is None:
                        return

                    results = await self._deliver_batch(
                        db, runtime, simulation, ids, event_ids, configs
                    )
                    attempts = runtime._attempt_buffer
                with get_session_factory()() as db:
                    db.info["batch_writes"] = True
                    runtime = SimulationRuntimeService(
                        db, self.products, self.transport, self.encryptor
                    )
                    db.add_all(attempts)
                    db.flush()
                    simulation = db.get(Simulation, simulation_id)
                    if simulation is None:
                        return
                    for job_id, result in zip(ids, results, strict=True):
                        finished_job = db.get(DeliveryJob, job_id)
                        event = db.get(EventInstance, event_ids[job_id])
                        if finished_job is None or event is None:
                            continue
                        finished_job.status = "delivered" if result.success else "failed"
                        finished_job.completed_at = datetime.now(UTC)
                        runtime._record_target_result(simulation, event, configs[job_id], result)
                        db.flush()
                        remaining = (
                            db.query(DeliveryJob)
                            .filter(
                                DeliveryJob.event_id == event.id,
                                DeliveryJob.status.in_(["pending", "active"]),
                            )
                            .count()
                        )
                        if remaining == 0 and event.status == "pending":
                            outcomes = event.simulator_metadata.get("target_results", {})
                            success = bool(outcomes) and all(
                                v["success"] for v in outcomes.values()
                            )
                            runtime._finalize_delivery(
                                simulation,
                                event,
                                result.model_copy(
                                    update={
                                        "success": success,
                                        "error_message": None
                                        if success
                                        else "One or more targets failed",
                                    }
                                ),
                            )
                    db.commit()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Target worker failed", extra={"target_key": key})
                with get_session_factory()() as db:
                    db.query(DeliveryJob).filter_by(target_key=key, status="active").update(
                        {"status": "pending"}
                    )
                    db.commit()
                await asyncio.sleep(1)

    async def _deliver_batch(
        self,
        db: Session,
        runtime: SimulationRuntimeService,
        simulation: Simulation,
        ids: list[str],
        event_ids: dict[str, str],
        configs: dict[str, dict[str, Any]],
    ) -> list[DeliveryResult]:
        if configs[ids[0]]["destination"].get("transport_id") in AZURE_TRANSPORTS and not (
            simulation.fault_config or {}
        ).get("enabled"):
            try:
                return await self._azure_batch(db, runtime, simulation, ids, event_ids, configs)
            except Exception:
                results = []
                for job_id in ids:
                    result = runtime._failure("Azure batch failed; verify record and DCR mappings")
                    event = db.get(EventInstance, event_ids[job_id])
                    if event is not None:
                        runtime._persist_attempt(
                            event,
                            result,
                            configs[job_id]["destination"]["transport_id"],
                            target_id=configs[job_id]["id"],
                        )
                    results.append(result)
                return results

        async def deliver(job_id: str) -> DeliveryResult:
            event = db.get(EventInstance, event_ids[job_id])
            if event is None:
                return runtime._failure("Event no longer exists")
            scenario = self.products.get_scenario(simulation.product_id, event.scenario_id)
            try:
                return await runtime._deliver_target(
                    simulation,
                    scenario,
                    event.payload,
                    event=event,
                    target=configs[job_id],
                )
            except Exception:
                result = runtime._failure(
                    "Target delivery failed; verify format and collector configuration"
                )
                runtime._persist_attempt(
                    event,
                    result,
                    configs[job_id]["destination"].get("transport_id", "http_webhook"),
                    target_id=configs[job_id]["id"],
                )
                return result

        return list(await asyncio.gather(*(deliver(job_id) for job_id in ids)))

    async def _azure_batch(
        self,
        db: Session,
        runtime: SimulationRuntimeService,
        simulation: Simulation,
        ids: list[str],
        event_ids: dict[str, str],
        configs: dict[str, dict[str, Any]],
    ) -> list[DeliveryResult]:
        target = configs[ids[0]]
        destination = destination_for_delivery(
            target["destination"], target.get("destination_secret_values", {}), self.encryptor
        )
        auth = self.encryptor.decrypt_auth_config(target.get("auth_config", {}))
        limit = min(int(destination.get("batch_max_bytes", 950000)), 950000)
        records: list[dict[str, Any]] = []
        groups: list[tuple[list[str], list[dict[str, Any]]]] = []
        group_ids: list[str] = []
        size = 2
        for job_id in ids:
            event = db.get(EventInstance, event_ids[job_id])
            assert event is not None
            body = ingestion_record(
                event.payload, target.get("payload_format", "default"), simulation.product_id
            )
            encoded_size = len(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode())
            if records and size + encoded_size + 1 > limit:
                groups.append((group_ids, records))
                group_ids, records, size = [], [], 2
            group_ids.append(job_id)
            records.append(body)
            size += encoded_size + bool(len(records) > 1)
        if records:
            groups.append((group_ids, records))
        outcomes: dict[str, DeliveryResult] = {}
        for batch_ids, batch_records in groups:
            result = await self.transport.deliver(
                destination, batch_records, "application/json", auth
            )
            for job_id in batch_ids:
                event = db.get(EventInstance, event_ids[job_id])
                assert event is not None
                runtime._persist_attempt(
                    event, result, "azure_logs_ingestion", target_id=target["id"]
                )
                outcomes[job_id] = result
        return [outcomes[job_id] for job_id in ids]
