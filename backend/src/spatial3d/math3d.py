from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class Vec3:
    x: float
    y: float
    z: float

    def __add__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> "Vec3":
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    __rmul__ = __mul__

    def dot(self, other: "Vec3") -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def norm_squared(self) -> float:
        return self.dot(self)

    def norm(self) -> float:
        return math.sqrt(self.norm_squared())

    def normalized(self) -> "Vec3":
        length = self.norm()
        if length == 0.0:
            raise ValueError("zero vector has no direction")
        return self * (1.0 / length)

    def distance_to(self, other: "Vec3") -> float:
        return (other - self).norm()
