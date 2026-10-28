import re


class MockExtractor:
    """Extract basic news signals using deterministic keyword rules."""

    COMPANIES = [
        "Microsoft",
        "Google",
        "Amazon",
        "AWS",
        "Meta",
        "OVH",
        "Oracle",
        "IBM",
        "Equinix",
        "Digital Realty",
        "NTT",
        "Telehouse",
        "nLighten",
        "Skaylink",
        "Telekom",
        "Hetzner",
        "SAP",
    ]

    CITIES = [
        "Berlin",
        "Cologne",
        "Köln",
        "Düsseldorf",
        "Elsdorf",
        "Frankfurt",
        "Hamburg",
        "Aachen",
        "Dortmund",
        "Bonn",
        "Essen",
    ]

    def extract(self, article):

        text = (
            article["title"]
            + " "
            + article["summary"]
        )

        company = self.find_company(text)
        city = self.find_city(text)

        return {

            "article_id": article["id"],

            "article_url": article.get(
                "url"
            ),

            "company": company,

            "facility": "",

            "city": city,

            "country": "Germany",

            "investment_signal":
                self.contains(
                    text,
                    [
                        "investment",
                        "invest",
                        "million",
                        "billion",
                        "funding",
                    ]
                ),

            "expansion_signal":
                self.contains(
                    text,
                    [
                        "expand",
                        "expansion",
                        "new campus",
                        "growth",
                    ]
                ),

            "retrofit_signal":
                self.contains(
                    text,
                    [
                        "retrofit",
                        "modernization",
                        "upgrade",
                    ]
                ),

            "renewable_signal":
                self.contains(
                    text,
                    [
                        "renewable",
                        "solar",
                        "wind",
                        "green energy",
                    ]
                ),

            "power_signal":
                self.contains(
                    text,
                    [
                        "power",
                        "grid",
                        "substation",
                        "electricity",
                        "energy",
                    ]
                ),

            "capacity_mw": None,

            "confidence": 0.50,
        }

    def find_company(self, text):

        for company in self.COMPANIES:

            if company.lower() in text.lower():

                return company

        return ""

    def find_city(self, text):

        for city in self.CITIES:

            if city.lower() in text.lower():

                return city

        return ""

    @staticmethod
    def contains(text, words):

        text = text.lower()

        return any(
            word.lower() in text
            for word in words
        )