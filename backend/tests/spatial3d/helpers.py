from spatial3d import (
    BodyConstants,
    GroundRole,
    GroundSite,
    LinkLimits,
    OrbitEnvironment,
    OrbitalPlane,
    Satellite,
    SpatialSpecification,
)


def minimal_spec() -> SpatialSpecification:
    return SpatialSpecification(
        body=BodyConstants(6371.0, 398600.435507, 86164.09054),
        orbit=OrbitEnvironment(550.0, 87.0, 12.0),
        links=LinkLimits(10.0, 3000.0),
        launch_stage=1,
        planes=(OrbitalPlane("P1", 0.0, 0.0),),
        satellites=(Satellite("S1", "P1", 0.0, 1),),
        ground_sites=(
            GroundSite("G1", "gateway", GroundRole.GATEWAY, 68.97, 33.07),
            GroundSite("C1", "client", GroundRole.CLIENT, 65.0, 60.0),
        ),
    )
