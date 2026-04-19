from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SchemeTopic(StrEnum):
    AGRICULTURE = "Agriculture"
    ANIMAL_HUSBANDRY = "Animal Husbandry"
    FISHERIES = "Fisheries"
    HORTICULTURE = "Horticulture"
    RURAL_DEVELOPMENT = "Rural Development"
    URBAN_DEVELOPMENT = "Urban Development"
    HOUSING = "Housing"
    INFRASTRUCTURE = "Infrastructure"
    EDUCATION = "Education"
    SKILL_DEVELOPMENT = "Skill Development"
    EMPLOYMENT = "Employment"
    ENTREPRENEURSHIP = "Entrepreneurship"
    HEALTHCARE = "Healthcare"
    NUTRITION = "Nutrition"
    WOMEN_WELFARE = "Women Welfare"
    CHILD_WELFARE = "Child Welfare"
    SOCIAL_WELFARE = "Social Welfare"
    DISABILITY_SUPPORT = "Disability Support"
    SENIOR_CITIZENS = "Senior Citizens"
    FINANCIAL_INCLUSION = "Financial Inclusion"
    ENVIRONMENT = "Environment"
    ENERGY = "Energy"
    SCIENCE_AND_RESEARCH = "Science & Research"
    SPORTS = "Sports"
    CULTURE = "Culture"


class TopicDefinition(BaseModel):
    """Definition of one controlled scheme topic and its indicative terms."""

    model_config = ConfigDict(frozen=True)

    topic: SchemeTopic
    slug: str
    description: str
    indicative_terms: tuple[str, ...] = Field(default_factory=tuple)

    @property
    def label(self) -> str:
        return self.topic.value


class TopicCatalog(BaseModel):
    """Immutable catalog of controlled topics used across enrichment and retrieval."""

    model_config = ConfigDict(frozen=True)

    topics: tuple[TopicDefinition, ...]
    note: str | None = None

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(topic.label for topic in self.topics)

    def description_lines(self) -> tuple[str, ...]:
        return tuple(
            f"{topic.label}: {topic.description}" for topic in self.topics
        )


TOPIC_COUNT_NOTE = (
    "The earlier taxonomy note said 22 topics, but the explicit topic list "
    "contains 25 labels. This catalog preserves the full agreed list for now "
    "and keeps the mismatch visible for later consolidation."
)


SCHEME_TOPIC_CATALOG = TopicCatalog(
    note=TOPIC_COUNT_NOTE,
    topics=(
        TopicDefinition(
            topic=SchemeTopic.AGRICULTURE,
            slug="agriculture",
            description="Farming support, crop production, irrigation, seeds, and farm inputs.",
            indicative_terms=("crop", "farmer", "seed", "soil", "irrigation"),
        ),
        TopicDefinition(
            topic=SchemeTopic.ANIMAL_HUSBANDRY,
            slug="animal-husbandry",
            description="Livestock, dairy, poultry, fodder, and animal care support.",
            indicative_terms=("livestock", "dairy", "cattle", "goat", "poultry"),
        ),
        TopicDefinition(
            topic=SchemeTopic.FISHERIES,
            slug="fisheries",
            description="Fishing, aquaculture, marine livelihoods, and fishery infrastructure.",
            indicative_terms=("fisher", "aquaculture", "marine", "pond", "fish"),
        ),
        TopicDefinition(
            topic=SchemeTopic.HORTICULTURE,
            slug="horticulture",
            description="Fruits, vegetables, floriculture, nurseries, and orchard support.",
            indicative_terms=("orchard", "floriculture", "fruit", "vegetable", "nursery"),
        ),
        TopicDefinition(
            topic=SchemeTopic.RURAL_DEVELOPMENT,
            slug="rural-development",
            description="Village livelihoods, self-help groups, rural infrastructure, and local development.",
            indicative_terms=("village", "gram", "rural", "self help group", "livelihood"),
        ),
        TopicDefinition(
            topic=SchemeTopic.URBAN_DEVELOPMENT,
            slug="urban-development",
            description="City services, municipal development, urban livelihoods, and town planning.",
            indicative_terms=("urban", "municipal", "city", "town", "street vendor"),
        ),
        TopicDefinition(
            topic=SchemeTopic.HOUSING,
            slug="housing",
            description="Homes, shelters, hostels, residential assistance, and housing finance.",
            indicative_terms=("house", "home", "shelter", "hostel", "residential"),
        ),
        TopicDefinition(
            topic=SchemeTopic.INFRASTRUCTURE,
            slug="infrastructure",
            description="Public works, transport, water, sanitation, and built facilities.",
            indicative_terms=("road", "bridge", "water", "sanitation", "construction"),
        ),
        TopicDefinition(
            topic=SchemeTopic.EDUCATION,
            slug="education",
            description="Schooling, scholarships, higher studies, tuition support, and academic access.",
            indicative_terms=("scholarship", "student", "college", "school", "tuition"),
        ),
        TopicDefinition(
            topic=SchemeTopic.SKILL_DEVELOPMENT,
            slug="skill-development",
            description="Vocational training, apprenticeships, certification, and job-readiness programs.",
            indicative_terms=("training", "skill", "apprentice", "iti", "certification"),
        ),
        TopicDefinition(
            topic=SchemeTopic.EMPLOYMENT,
            slug="employment",
            description="Jobs, wage support, placement, unemployment relief, and work opportunities.",
            indicative_terms=("job", "employment", "placement", "wage", "unemployment"),
        ),
        TopicDefinition(
            topic=SchemeTopic.ENTREPRENEURSHIP,
            slug="entrepreneurship",
            description="Businesses, startups, self-employment, enterprise finance, and incubation.",
            indicative_terms=("startup", "business", "enterprise", "self employment", "msme"),
        ),
        TopicDefinition(
            topic=SchemeTopic.HEALTHCARE,
            slug="healthcare",
            description="Medical treatment, insurance, disease support, public health, and care access.",
            indicative_terms=("medical", "health", "hospital", "treatment", "insurance"),
        ),
        TopicDefinition(
            topic=SchemeTopic.NUTRITION,
            slug="nutrition",
            description="Food support, supplements, maternal nutrition, and child nourishment.",
            indicative_terms=("nutrition", "food", "meal", "malnutrition", "supplement"),
        ),
        TopicDefinition(
            topic=SchemeTopic.WOMEN_WELFARE,
            slug="women-welfare",
            description="Programs focused on women’s safety, support, income, health, and empowerment.",
            indicative_terms=("women", "mahila", "girl", "maternal", "sanitary"),
        ),
        TopicDefinition(
            topic=SchemeTopic.CHILD_WELFARE,
            slug="child-welfare",
            description="Child development, childcare, protection, and education-linked child support.",
            indicative_terms=("child", "children", "anganwadi", "infant", "pre school"),
        ),
        TopicDefinition(
            topic=SchemeTopic.SOCIAL_WELFARE,
            slug="social-welfare",
            description="Broad social protection, assistance, pension, relief, and welfare measures.",
            indicative_terms=("welfare", "assistance", "relief", "pension", "support"),
        ),
        TopicDefinition(
            topic=SchemeTopic.DISABILITY_SUPPORT,
            slug="disability-support",
            description="Benefits, education, assistive support, and inclusion for persons with disabilities.",
            indicative_terms=("disability", "disabled", "pwd", "assistive", "special needs"),
        ),
        TopicDefinition(
            topic=SchemeTopic.SENIOR_CITIZENS,
            slug="senior-citizens",
            description="Support schemes for older adults, pensions, care, and senior welfare.",
            indicative_terms=("senior citizen", "elderly", "old age", "retirement", "aged"),
        ),
        TopicDefinition(
            topic=SchemeTopic.FINANCIAL_INCLUSION,
            slug="financial-inclusion",
            description="Banking access, credit, savings, microfinance, and account-linked inclusion.",
            indicative_terms=("bank", "account", "credit", "microfinance", "loan"),
        ),
        TopicDefinition(
            topic=SchemeTopic.ENVIRONMENT,
            slug="environment",
            description="Conservation, ecology, climate resilience, waste management, and sustainability.",
            indicative_terms=("environment", "climate", "forest", "waste", "sustainability"),
        ),
        TopicDefinition(
            topic=SchemeTopic.ENERGY,
            slug="energy",
            description="Electricity, renewable energy, power access, and energy efficiency initiatives.",
            indicative_terms=("solar", "electricity", "power", "renewable", "energy"),
        ),
        TopicDefinition(
            topic=SchemeTopic.SCIENCE_AND_RESEARCH,
            slug="science-research",
            description="Research grants, innovation, fellowships, patents, and scientific development.",
            indicative_terms=("research", "innovation", "patent", "scientific", "fellowship"),
        ),
        TopicDefinition(
            topic=SchemeTopic.SPORTS,
            slug="sports",
            description="Athlete support, coaching, sports infrastructure, and participation programs.",
            indicative_terms=("sports", "athlete", "coach", "stadium", "training"),
        ),
        TopicDefinition(
            topic=SchemeTopic.CULTURE,
            slug="culture",
            description="Arts, heritage, crafts, language, and cultural preservation or promotion.",
            indicative_terms=("art", "artist", "craft", "heritage", "culture"),
        ),
    ),
)

CONTROLLED_TOPICS: tuple[str, ...] = SCHEME_TOPIC_CATALOG.labels
CONTROLLED_TOPIC_SET = frozenset(CONTROLLED_TOPICS)
TOPIC_DESCRIPTION_BY_LABEL: dict[str, str] = {
    definition.label: definition.description
    for definition in SCHEME_TOPIC_CATALOG.topics
}
