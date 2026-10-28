from sqlalchemy.orm import Session

from app.database.repositories.energy_asset_repository import (
    EnergyAssetRepository,
)
from app.database.repositories.facility_repository import (
    FacilityRepository,
)
from app.database.repositories.land_value_repository import (
    LandValueRepository,
)
from app.database.repositories.power_infrastructure_repository import (
    PowerInfrastructureRepository,
)
from app.services.site_score_service import SiteScoreService

class SiteIntelligenceService:
    """
    Service responsible for analyzing a facility using
    multiple spatial datasets.

    This service contains NO SQL.
    It only orchestrates repository calls.
    """

    def __init__(self, session: Session):

        self.session = session

        self.facility_repository = FacilityRepository(session)

        self.power_repository = (
            PowerInfrastructureRepository(session)
        )

        self.land_repository = (
            LandValueRepository(session)
        )

        self.energy_repository = (
            EnergyAssetRepository(session)
        )

    # ======================================================
    # Facility Intelligence
    # ======================================================

    def analyze_facility(
        self,
        facility_id: int,
    ) -> dict | None:
        """
        Returns complete site intelligence
        for a facility.
        """

        facility = self.facility_repository.find_by_id(
            facility_id
        )

        if facility is None:
            return None

        return self.analyze_location(
            latitude=facility.latitude,
            longitude=facility.longitude,
            facility=facility,
        )

    # ======================================================
    # Location Intelligence
    # ======================================================

    def analyze_location(
        self,
        latitude: float,
        longitude: float,
        facility=None,
    ) -> dict:
        """
        Analyze any arbitrary location.

        This allows future support for:
        - User-selected map locations
        - Candidate sites
        """

        nearest_substation = (
            self.power_repository.find_nearest_substation(
                latitude,
                longitude,
            )
        )

        nearest_line = (
            self.power_repository.find_nearest_high_voltage_line(
                latitude,
                longitude,
            )
        )

        nearest_transformer = (
            self.power_repository.find_nearest_transformer(
                latitude,
                longitude,
            )
        )

        nearest_land_value = (
            self.land_repository.find_nearest_land_value(
                latitude,
                longitude,
            )
        )

        nearby_energy = (
            self.energy_repository.find_energy_capacity(
                latitude,
                longitude,
            )
        )

        intelligence = {

            "facility": facility,

            "location": {
                "latitude": latitude,
                "longitude": longitude,
            },

            "power": {

                "nearest_substation":
                    nearest_substation,

                "nearest_high_voltage_line":
                    nearest_line,

                "nearest_transformer":
                    nearest_transformer,
            },

            "land": {
                "municipality": (
                    nearest_land_value["municipality"]
                    if nearest_land_value
                    else None
                ),
                "district": (
                    nearest_land_value["district"]
                    if nearest_land_value
                    else None
                ),
                "postal_code": (
                    nearest_land_value["postal_code"]
                    if nearest_land_value
                    else None
                ),
                "land_value_eur_m2": (
                    nearest_land_value["land_value_eur_m2"]
                    if nearest_land_value
                    else None
                ),
                "distance_km": (
                    nearest_land_value["distance_km"]
                    if nearest_land_value
                    else None
                ),
            },

            "renewable_energy":
                nearby_energy,
        }

        score = SiteScoreService.calculate(
            intelligence
        )

        # If SiteScoreResult has to_dict()
        intelligence["site_score"] = score.to_dict()

        # Otherwise use:
        # intelligence["site_score"] = asdict(score)

        return intelligence

    # ======================================================
    # Future Site Score
    # ======================================================

    def calculate_site_score(
        self,
        intelligence: dict,
    ) -> dict:
        """
        Placeholder for future Site Scoring Engine.
        """

        return {
            "overall": None,
            "power": None,
            "land": None,
            "renewable": None,
        }
    def compare_companies(
        self,
        company_a: str,
        company_b: str,
    ) -> dict:
        """
        Compare two companies using the available
        Business Intelligence data.
        """

        left = self.company_sites(company_a)

        right = self.company_sites(company_b)

        return {
            "left": left,
            "right": right,
        }

    def company_sites(
        self,
        company: str,
    ) -> list[dict]:
        """
        Returns all facilities for a company.
        """

        facilities = self.facility_repository.find_by_company(
            company
        )

        return [
            {
                "id": facility.id,
                "company": facility.company,
                "name": facility.name,
                "city": facility.city,
                "country": facility.country,
                "address": facility.address,
                "website": facility.website,
            }
            for facility in facilities
        ]