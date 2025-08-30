from typing import List, Literal, Dict, Optional
from pydantic import BaseModel, Field

class SchemeDetails(BaseModel):
    url: str = Field(..., description="The URL of the scheme")
    name: str = Field(..., description="The name of the scheme")
    level: Literal["central", "state"] = Field(..., description="The level of the scheme"    )
    provider: str = Field(..., description="The provider of the scheme, could by a ministry or a state")
    tags: List[str] = Field(..., description="The tags of the scheme")
    details: str = Field(..., description="The details of the scheme")
    benefits: str = Field(..., description="The benefits of the scheme")
    eligibility: str = Field(..., description="The eligibility of the scheme")
    application_process: str = Field(..., description="The application process of the scheme")
    documents_required: str = Field(..., description="The documents required for the scheme")
    frequently_asked_questions: Dict[str, str] = Field(None, description="The frequently asked questions of the scheme")
    sources_and_references: Optional[List[Dict[str, str]]] = Field(None, description="The sources and references of the scheme")