from __future__ import annotations

from cosmo_a_json import ScenarioDto
from dynamic_model import DynamicAnalysis
from variant_comparison import ConfigurationParameter, VariantConfiguration, VariantInput


def configuration_from_scenario(scenario: ScenarioDto) -> VariantConfiguration:
    """Project the cosmo-A scenario into stable comparable leaf parameters.

    Collection members use semantic IDs rather than positional array indexes, so
    reordering JSON arrays does not appear as a project change.
    """

    e = scenario.environment
    d = scenario.design
    parameters: list[ConfigurationParameter] = [
        ConfigurationParameter("environment.altitude_km", e.altitude_km),
        ConfigurationParameter("environment.inclination_deg", e.inclination_deg),
        ConfigurationParameter("environment.earth_angle0_deg", e.earth_angle0_deg),
        ConfigurationParameter("environment.horizon_s", e.horizon_s),
        ConfigurationParameter("environment.step_s", e.step_s),
        ConfigurationParameter("environment.min_elevation_deg", e.min_elevation_deg),
        ConfigurationParameter("environment.isl_range_km", e.isl_range_km),
        ConfigurationParameter("environment.target_availability", e.target_availability),
        ConfigurationParameter("design.launch_stage", d.launch_stage),
    ]

    for plane in sorted(d.planes, key=lambda item: item.id):
        prefix = f"design.planes[{plane.id}]"
        parameters.extend((
            ConfigurationParameter(f"{prefix}.raan_deg", plane.raan_deg),
            ConfigurationParameter(f"{prefix}.phase_deg", plane.phase_deg),
        ))

    for satellite in sorted(d.satellites, key=lambda item: item.id):
        prefix = f"design.satellites[{satellite.id}]"
        parameters.extend((
            ConfigurationParameter(f"{prefix}.plane_id", satellite.plane_id),
            ConfigurationParameter(f"{prefix}.slot_deg", satellite.slot_deg),
            ConfigurationParameter(f"{prefix}.launch_batch", satellite.launch_batch),
        ))

    for site in sorted(scenario.ground_sites, key=lambda item: item.id):
        prefix = f"ground_sites[{site.id}]"
        parameters.extend((
            ConfigurationParameter(f"{prefix}.name", site.name),
            ConfigurationParameter(f"{prefix}.role", site.role),
            ConfigurationParameter(f"{prefix}.lat_deg", site.lat_deg),
            ConfigurationParameter(f"{prefix}.lon_deg", site.lon_deg),
        ))

    satellite_failures: dict[str, list[str]] = {}
    for failure in scenario.failures:
        satellite_failures.setdefault(failure.satellite_id, []).append(
            f"{failure.start_s}:{failure.end_s}"
        )
    for satellite_id, intervals in sorted(satellite_failures.items()):
        parameters.append(ConfigurationParameter(
            f"failures[{satellite_id}]",
            tuple(sorted(intervals)),
        ))

    gateway_outages: dict[str, list[str]] = {}
    for outage in scenario.gateway_outages:
        gateway_outages.setdefault(outage.gateway_id, []).append(
            f"{outage.start_s}:{outage.end_s}"
        )
    for gateway_id, intervals in sorted(gateway_outages.items()):
        parameters.append(ConfigurationParameter(
            f"gateway_outages[{gateway_id}]",
            tuple(sorted(intervals)),
        ))

    return VariantConfiguration(tuple(parameters))


def variant_from_scenario(scenario: ScenarioDto, analysis: DynamicAnalysis) -> VariantInput:
    return VariantInput(
        variant_id=scenario.meta.id,
        title=scenario.meta.title,
        configuration=configuration_from_scenario(scenario),
        analysis=analysis,
    )
