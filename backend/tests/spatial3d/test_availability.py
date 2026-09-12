from dataclasses import replace

from spatial3d import (
    DeploymentAndOutageSatelliteAvailability,
    GatewayOutage,
    GatewayOutageGroundAvailability,
    Interval,
    SatelliteOutage,
)
from .helpers import minimal_spec


def test_satellite_outage_is_half_open() -> None:
    spec = minimal_spec()
    spec = replace(spec, satellite_outages=(SatelliteOutage("S1", Interval(10.0, 20.0)),))
    policy = DeploymentAndOutageSatelliteAvailability()
    sat = spec.satellites[0]
    assert policy.active(spec, sat, 9.999)
    assert not policy.active(spec, sat, 10.0)
    assert not policy.active(spec, sat, 19.999)
    assert policy.active(spec, sat, 20.0)


def test_launch_stage_is_filter() -> None:
    spec = minimal_spec()
    sat = replace(spec.satellites[0], launch_batch=2)
    assert not DeploymentAndOutageSatelliteAvailability().active(spec, sat, 0.0)


def test_gateway_outage_does_not_disable_clients() -> None:
    spec = minimal_spec()
    spec = replace(spec, gateway_outages=(GatewayOutage("G1", Interval(0.0, 10.0)),))
    policy = GatewayOutageGroundAvailability()
    gateway, client = spec.ground_sites
    assert not policy.available(spec, gateway, 0.0)
    assert policy.available(spec, client, 0.0)
