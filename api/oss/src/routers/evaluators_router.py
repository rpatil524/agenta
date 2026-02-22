from typing import List

from oss.src.models.api.evaluation_model import LegacyEvaluator
from oss.src.resources.evaluators.evaluators import get_all_evaluators
from oss.src.utils.common import APIRouter

router = APIRouter()

# Load builtin evaluators once at module load
BUILTIN_EVALUATORS: List[LegacyEvaluator] = [
    LegacyEvaluator(**evaluator_dict) for evaluator_dict in get_all_evaluators()
]


@router.get("/", response_model=List[LegacyEvaluator])
async def get_evaluators_endpoint():
    return BUILTIN_EVALUATORS
