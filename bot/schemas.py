from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any, List
from datetime import datetime

class DeviceSchema(BaseModel):
    id: int
    aibox_id: str
    name: Optional[str]
    desc: Optional[str]

class SourceSchema(BaseModel):
    id: int
    source_id: str
    ipv4: str
    desc: Optional[str]

class AlgorithmSchema(BaseModel):
    id: int
    key: str
    name: str
    type: Optional[str]

class CompanySchema(BaseModel):
    id: int
    name: str
    description: Optional[str]

class AlertSchema(BaseModel):
    id: int
    aibox_alert_id: str
    alert_time: datetime
    device: DeviceSchema
    source: SourceSchema
    alg: AlgorithmSchema
    hazard_level: Optional[str] = ""
    image: Optional[HttpUrl] = None
    video: Optional[str] = None
    reserved_data: Optional[Dict[str, Any]] = {}
    company: CompanySchema
    users_telegram_id: List[int]
    for_security: bool
