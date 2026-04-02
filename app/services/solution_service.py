import structlog

from app.providers.llm.base import LLMProvider
from app.repositories.problem_repository import ProblemRepository

logger = structlog.get_logger()


class SolutionService:
    """Generates AI solution approaches for approved problems."""

    def __init__(
        self, llm_provider: LLMProvider, problem_repo: ProblemRepository
    ) -> None:
        self._llm_provider = llm_provider
        self._problem_repo = problem_repo

    async def generate_and_store(self, problem_id: str) -> str | None:
        """Generate an AI solution approach and persist it to the database.

        Fetches the problem, calls the LLM to generate a Markdown solution,
        then inserts it as an approved, AI-generated solution approach.

        Args:
            problem_id: UUID of the approved problem.

        Returns:
            UUID of the created solution_approach row, or None if problem not found.
        """
        log = logger.bind(problem_id=problem_id)

        problem = await self._problem_repo.get_by_id(problem_id)
        if problem is None:
            log.warning("solution_generation_skipped_problem_not_found")
            return None

        description = problem.get("description_en") or problem.get("description", "")

        log.debug("generating_ai_solution")
        content = await self._llm_provider.generate_solution(
            problem_title=problem["title"],
            problem_description=description,
        )

        solution_id = await self._problem_repo.create_solution(problem_id, content)
        log.info("ai_solution_stored", solution_id=solution_id)
        return solution_id
