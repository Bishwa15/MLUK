"""
Intelligence Search Service

Responsible for querying the NRW Data Center
Business Intelligence database.


Author:
NRW BI Platform
"""

from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.models.facility import Facility
from app.database.repositories.facility_repository import (
    FacilityRepository,
)

class IntelligenceSearchService:

    def __init__(self, session: Session):
        self.session = session

    # =====================================================
    # Facility Searches
    # =====================================================

    def search_by_city(self, city: str):
        raise NotImplementedError()

    def search_by_company(
        self,
        company: str,
    ) -> list[dict]:

        facilities = (
            self._base_query()
            .filter(
                Facility.company.ilike(f"%{company}%")
            )
            .order_by(
                Facility.name,
            )
            .all()
        )

        return [
            self._facility_to_dict(f)
            for f in facilities
        ]

    def search_by_country(
        self,
        country: str,
    ) -> list[dict]:

        facilities = (
            self._base_query()
            .filter(
                Facility.country.ilike(f"%{country}%")
            )
            .order_by(
                Facility.company,
                Facility.name,
            )
            .all()
        )

        return [
            self._facility_to_dict(f)
            for f in facilities
        ]

    # =====================================================
    # Nearby Search
    # =====================================================

    def search_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 25,
    ) -> list[dict]:
        """
        Search facilities near a geographic location.
        """

        repository = FacilityRepository(
            self.session,
        )

        facilities = repository.find_nearby(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
        )

        return [
            self._facility_to_dict(
                facility,
            )
            for facility in facilities
        ]
   

    # =====================================================
    # Site Intelligence
    # =====================================================

    def search_by_site_score(
        self,
        minimum_score: float,
    ):
        raise NotImplementedError()

    def search_by_grid_score(
        self,
        minimum_score: float,
    ):
        raise NotImplementedError()

    def search_by_transmission_score(
        self,
        minimum_score: float,
    ):
        raise NotImplementedError()

    def search_by_transformer_score(
        self,
        minimum_score: float,
    ):
        raise NotImplementedError()

    def search_by_land_score(
        self,
        minimum_score: float,
    ):
        raise NotImplementedError()

    def search_by_expansion_score(
        self,
        minimum_score: float,
    ):
        raise NotImplementedError()

    def search_by_renewable_score(
        self,
        minimum_score: float,
    ):
        raise NotImplementedError()

    # =====================================================
    # Infrastructure
    # =====================================================

    def search_by_voltage(
        self,
        voltage: str,
    ):
        raise NotImplementedError()

    def search_by_substation_distance(
        self,
        max_distance: float,
    ):
        raise NotImplementedError()

    def search_by_transformer_distance(
        self,
        max_distance: float,
    ):
        raise NotImplementedError()

    # =====================================================
    # Land
    # =====================================================

    def search_by_land_value(
        self,
        maximum_price: float,
    ):
        raise NotImplementedError()

    # =====================================================
    # Renewable
    # =====================================================

    def search_by_solar_capacity(
        self,
        minimum_kw: float,
    ):
        raise NotImplementedError()

    def search_by_wind_capacity(
        self,
        minimum_kw: float,
    ):
        raise NotImplementedError()

    # =====================================================
    # Ranking
    # =====================================================

    def top_sites(
        self,
        limit: int = 10,
    ):
        raise NotImplementedError()

    def latest_sites(
        self,
        limit: int = 10,
    ):
        raise NotImplementedError()

    # =====================================================
    # Compare
    # =====================================================

    def get_site(
        self,
        facility_id: int,
    ) -> dict | None:

        facility = (
            self._base_query()
            .filter(
                Facility.id == facility_id
            )
            .first()
        )

        if not facility:
            return None

        return self._facility_to_dict(facility)

    def compare_sites(
        self,
        facility_ids: list[int],
    ):
        raise NotImplementedError()
     # =====================================================
    # Comparison Companies
    # =====================================================

    def compare_companies(
        self,
        company_a: str,
        company_b: str,
    ) -> dict:

        return {
            "left": self.search_by_company(company_a),
            "right": self.search_by_company(company_b),
        }

    # =====================================================
    # comparison sites
    # =====================================================
    def _compare_sites(
        self,
        question: str,
    ) -> str:

        return (
            "Site comparison is not yet available."
        )
    # =====================================================
    # Base Query
    # =====================================================

    def _base_query(self):

        return (
            self.session.query(Facility)
        )

    # =====================================================
    # Mapper
    # =====================================================

    def _facility_to_dict(
        self,
        facility: Facility,
    ) -> dict:

        return {
            "id": facility.id,
            "company": facility.company,
            "name": facility.name,
            "address": facility.address,
            "city": facility.city,
            "postal_code": facility.postal_code,
            "country": facility.country,
            "website": facility.website,
            "latitude": facility.latitude,
            "longitude": facility.longitude,
        }

    # =====================================================
    # Search by City
    # =====================================================

    def search_by_city(
        self,
        city: str,
    ) -> list[dict]:

        facilities = (
            self._base_query()
            .filter(
                Facility.city.ilike(f"%{city}%")
            )
            .order_by(
                Facility.company,
                Facility.name,
            )
            .all()
        )

        return [
            self._facility_to_dict(
                facility
            )
            for facility in facilities
        ]

   