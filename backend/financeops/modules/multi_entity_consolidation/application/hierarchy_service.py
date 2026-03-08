from __future__ import annotations

from collections import defaultdict, deque
from uuid import UUID


class HierarchyService:
    def deterministic_entity_order(self, *, nodes: list[object]) -> list[UUID]:
        by_id = {row.id: row for row in nodes}
        children: dict[UUID | None, list[UUID]] = defaultdict(list)
        indegree: dict[UUID, int] = {}
        for row in nodes:
            indegree[row.id] = 0
        for row in nodes:
            parent = row.parent_node_id
            if parent is not None:
                if parent not in by_id:
                    raise ValueError("Hierarchy node parent reference is invalid")
                children[parent].append(row.id)
                indegree[row.id] += 1
            else:
                children[None].append(row.id)

        for key in list(children):
            children[key].sort(key=lambda value: str(value))
        queue = deque(sorted([node for node, deg in indegree.items() if deg == 0], key=lambda value: str(value)))
        ordered_nodes: list[UUID] = []
        while queue:
            node = queue.popleft()
            ordered_nodes.append(node)
            for child in children.get(node, []):
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)
            queue = deque(sorted(queue, key=lambda value: str(value)))

        if len(ordered_nodes) != len(nodes):
            raise ValueError("Hierarchy cycle detected during traversal")
        return [by_id[node_id].entity_id for node_id in ordered_nodes]

