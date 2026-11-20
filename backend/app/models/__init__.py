"""Register every model with one shared Base.metadata."""
from app.models import _auth_reference  # noqa: F401
from app.models.DimUserProfile import DimUserProfile
from app.models.DimScenario import DimScenario
from app.models.DimQuestionnaire import DimQuestionnaire
from app.models.DimQuestion import DimQuestion
from app.models.DimFutureSelf import DimFutureSelf
from app.models.DimVoiceAsset import DimVoiceAsset
from app.models.FactProfileAnswer import FactProfileAnswer
from app.models.FactConversation import FactConversation
from app.models.FactMessage import FactMessage
from app.models.FactConsent import FactConsent
from app.models.FactAgentDebate import FactAgentDebate
from app.models.FactShare import FactShare
from app.models.FactPersonaVersion import FactPersonaVersion
from app.models.FactAiMemory import FactAiMemory
from app.models.FactMemoryFeedback import FactMemoryFeedback
