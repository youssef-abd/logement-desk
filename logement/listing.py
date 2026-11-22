from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class Listing:
    source: str
    source_id: str
    url: str
    title: str = ""
    rent_cc: Optional[float] = None
    charges: Optional[float] = None
    surface_m2: Optional[float] = None
    rooms: Optional[int] = None
    kind: Optional[str] = None
    district: Optional[str] = None
    postal_code: Optional[str] = None
    furnished: Optional[bool] = None
    poster: Optional[str] = None
    poster_name: Optional[str] = None  # the agency's name (never a private person's)
    published_at: Optional[str] = None
    description: str = ""
    photos: list = field(default_factory=list)
    flags: list = field(default_factory=list)
    tags: list = field(default_factory=list)
    found_by: str = ""
    city: Optional[str] = None  # the registry key of the city pass that found it
    match: bool = True  # meets the owner's own criteria (the collection net can be wider)

    @property
    def key(self):
        return f"{self.source}:{self.source_id}"

    def to_dict(self):
        return asdict(self)
