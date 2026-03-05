from __future__ import annotations

from collections import defaultdict, deque

from financeops.prompt_engine import PromptDefinition


class DependencyGraph:
    def __init__(self, prompts: list[PromptDefinition]) -> None:
        self.prompts = prompts
        self.prompt_map = {prompt.prompt_id: prompt for prompt in prompts}

    def topological_order(self) -> list[PromptDefinition]:
        self._validate_missing_dependencies()

        indegree: dict[str, int] = {prompt.prompt_id: 0 for prompt in self.prompts}
        children: dict[str, list[str]] = defaultdict(list)

        for prompt in self.prompts:
            for dep in prompt.dependencies:
                children[dep].append(prompt.prompt_id)
                indegree[prompt.prompt_id] += 1

        queue: deque[str] = deque(sorted([pid for pid, d in indegree.items() if d == 0]))
        ordered_ids: list[str] = []

        while queue:
            current = queue.popleft()
            ordered_ids.append(current)
            for child in children[current]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)

        if len(ordered_ids) != len(self.prompts):
            raise ValueError("Circular dependency detected in prompt catalog")

        return [self.prompt_map[prompt_id] for prompt_id in ordered_ids]

    def _validate_missing_dependencies(self) -> None:
        missing: list[str] = []
        for prompt in self.prompts:
            for dep in prompt.dependencies:
                if dep not in self.prompt_map:
                    missing.append(f"{prompt.prompt_id} -> {dep}")
        if missing:
            raise ValueError(
                "Missing dependency prompt IDs detected: " + ", ".join(sorted(missing))
            )

