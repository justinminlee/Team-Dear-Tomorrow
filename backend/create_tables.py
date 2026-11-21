# create_tables.py
from app.database.base import Base
from app.database.session import engine

from app.models.FactUser import FactUser
from app.models.DimChat import DimChat
from app.models.DimMsg import DimMsg
from app.models.DimQs import DimQs
from app.models.DimVoice import DimVoice

# Speaking style learning
from app.models.DimVoiceStyle import DimVoiceStyle
from app.models.FactSpeakingPattern import FactSpeakingPattern
from app.models.DimTranscript import DimTranscript
from app.models.FactTranscriptPattern import FactTranscriptPattern

Base.metadata.create_all(bind=engine)

print("Tables created successfully!")


