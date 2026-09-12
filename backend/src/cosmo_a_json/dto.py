from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class MetaDto(StrictModel):
    id: str
    title: str


class EnvironmentDto(StrictModel):
    altitude_km: float
    inclination_deg: float
    earth_angle0_deg: float
    horizon_s: int
    step_s: int
    min_elevation_deg: float
    isl_range_km: float
    target_availability: float


class PlaneDto(StrictModel):
    id: str
    raan_deg: float
    phase_deg: float


class SatelliteDto(StrictModel):
    id: str
    plane_id: str
    slot_deg: float
    launch_batch: int


class DesignDto(StrictModel):
    launch_stage: int
    planes: list[PlaneDto]
    satellites: list[SatelliteDto]


class GroundSiteDto(StrictModel):
    id: str
    name: str
    role: str
    lat_deg: float
    lon_deg: float


class SatelliteOutageDto(StrictModel):
    satellite_id: str
    start_s: int | float
    end_s: int | float


class GatewayOutageDto(StrictModel):
    gateway_id: str
    start_s: int | float
    end_s: int | float


class ScenarioDto(StrictModel):
    meta: MetaDto
    environment: EnvironmentDto
    design: DesignDto
    ground_sites: list[GroundSiteDto]
    failures: list[SatelliteOutageDto]
    gateway_outages: list[GatewayOutageDto]

    @model_validator(mode="after")
    def validate_case_contract(self) -> "ScenarioDto":
        e = self.environment
        if not 200 <= e.altitude_km <= 1200:
            raise ValueError("environment.altitude_km must be in [200, 1200]")
        if not 0 < e.inclination_deg <= 180:
            raise ValueError("environment.inclination_deg must be in (0, 180]")
        if not 0 < e.step_s <= e.horizon_s <= 172800 or e.horizon_s % e.step_s != 0:
            raise ValueError("environment time grid is invalid")
        if not 0 <= e.min_elevation_deg < 90:
            raise ValueError("environment.min_elevation_deg must be in [0, 90)")
        if not 0 < e.isl_range_km <= 10000:
            raise ValueError("environment.isl_range_km must be in (0, 10000]")
        if not 0 <= e.target_availability <= 1:
            raise ValueError("environment.target_availability must be in [0, 1]")
        if self.design.launch_stage not in (1, 2, 3):
            raise ValueError("design.launch_stage must be 1, 2 or 3")

        plane_ids = [plane.id for plane in self.design.planes]
        if not plane_ids or len(plane_ids) != len(set(plane_ids)):
            raise ValueError("design.planes ids must be non-empty and unique")
        for plane in self.design.planes:
            if not 0 <= plane.raan_deg < 360 or not 0 <= plane.phase_deg < 360:
                raise ValueError("plane angles must be in [0, 360)")

        satellite_ids = [satellite.id for satellite in self.design.satellites]
        if not satellite_ids or len(satellite_ids) != len(set(satellite_ids)):
            raise ValueError("design.satellites ids must be non-empty and unique")
        known_planes = set(plane_ids)
        for satellite in self.design.satellites:
            if satellite.plane_id not in known_planes:
                raise ValueError(f"unknown satellite plane: {satellite.plane_id}")
            if satellite.launch_batch not in (1, 2, 3):
                raise ValueError("satellite launch_batch must be 1, 2 or 3")

        ground_ids = [site.id for site in self.ground_sites]
        if len(ground_ids) != len(set(ground_ids)) or set(ground_ids) & set(satellite_ids):
            raise ValueError("ground and satellite node ids must be globally unique")
        if not any(site.role == "client" for site in self.ground_sites):
            raise ValueError("at least one client is required")
        if not any(site.role == "gateway" for site in self.ground_sites):
            raise ValueError("at least one gateway is required")
        for site in self.ground_sites:
            if site.role not in ("client", "gateway"):
                raise ValueError(f"unsupported ground role: {site.role}")
            if not -90 <= site.lat_deg <= 90 or not -180 <= site.lon_deg <= 180:
                raise ValueError("ground coordinates are out of range")

        known_satellites = set(satellite_ids)
        known_gateways = {site.id for site in self.ground_sites if site.role == "gateway"}
        for failure in self.failures:
            if failure.satellite_id not in known_satellites:
                raise ValueError(f"unknown satellite in failure: {failure.satellite_id}")
            if not 0 <= failure.start_s < failure.end_s <= e.horizon_s:
                raise ValueError("satellite failure interval is outside the horizon")
        for outage in self.gateway_outages:
            if outage.gateway_id not in known_gateways:
                raise ValueError(f"unknown gateway in outage: {outage.gateway_id}")
            if not 0 <= outage.start_s < outage.end_s <= e.horizon_s:
                raise ValueError("gateway outage interval is outside the horizon")
        return self
