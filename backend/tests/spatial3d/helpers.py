from spatial3d import (
    BodyConstants,
    CircularOrbitAssignment,
    CircularOrbitConfiguration,
    CircularOrbitEnvironment,
    CircularOrbitTrajectory,
    GroundRole,
    GroundSite,
    LinkLimits,
    OrbitalPlane,
    Satellite,
    SpatialSpecification,
)


def minimal_spec() -> SpatialSpecification:
    return SpatialSpecification(
        body=BodyConstants(6371.0),
        links=LinkLimits(10.0, 3000.0),
        launch_stage=1,
        satellites=(Satellite("S1", 1),),
        ground_sites=(
            GroundSite("G1", "gateway", GroundRole.GATEWAY, 68.97, 33.07),
            GroundSite("C1", "client", GroundRole.CLIENT, 65.0, 60.0),
        ),
    )


def minimal_trajectory(spec: SpatialSpecification | None = None) -> CircularOrbitTrajectory:
    actual = spec or minimal_spec()
    return CircularOrbitTrajectory(
        actual.body,
        CircularOrbitConfiguration(
            environment=CircularOrbitEnvironment(
                550.0,
                87.0,
                12.0,
                398600.435507,
                86164.09054,
            ),
            planes=(OrbitalPlane("P1", 0.0, 0.0),),
            assignments=tuple(
                CircularOrbitAssignment(satellite.id, "P1", index * 22.5)
                for index, satellite in enumerate(actual.satellites)
            ),
        ),
    )
