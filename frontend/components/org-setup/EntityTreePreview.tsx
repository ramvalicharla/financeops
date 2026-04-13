"use client"

import { Building2 } from "lucide-react"

interface EntityNode {
  id: string
  name: string
  type: string
  parentId?: string
}

interface EntityTreePreviewProps {
  entities: EntityNode[]
  orgName: string
}

interface TreeNode extends EntityNode {
  children: TreeNode[]
}

function buildTree(entities: EntityNode[]): TreeNode[] {
  const map = new Map<string, TreeNode>()
  const roots: TreeNode[] = []

  for (const entity of entities) {
    map.set(entity.id, { ...entity, children: [] })
  }

  for (const entity of entities) {
    const node = map.get(entity.id)!
    if (entity.parentId && map.has(entity.parentId)) {
      map.get(entity.parentId)!.children.push(node)
    } else {
      roots.push(node)
    }
  }

  return roots
}

const TYPE_BADGE: Record<string, string> = {
  WHOLLY_OWNED_SUBSIDIARY:
    "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  BRANCH:
    "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
  REPRESENTATIVE_OFFICE:
    "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
  HOLDING_COMPANY:
    "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
  ASSOCIATE:
    "bg-teal-100 text-teal-800 dark:bg-teal-900/30 dark:text-teal-300",
  JOINT_VENTURE:
    "bg-teal-100 text-teal-800 dark:bg-teal-900/30 dark:text-teal-300",
}

const TYPE_LABEL: Record<string, string> = {
  WHOLLY_OWNED_SUBSIDIARY: "Subsidiary",
  JOINT_VENTURE: "JV",
  ASSOCIATE: "Associate",
  BRANCH: "Branch",
  REPRESENTATIVE_OFFICE: "Rep. Office",
  HOLDING_COMPANY: "Holding",
  PARTNERSHIP: "Partnership",
  LLP: "LLP",
  TRUST: "Trust",
  SOLE_PROPRIETORSHIP: "Sole Prop.",
}

function EntityRow({ node }: { node: TreeNode }) {
  const badgeClass =
    TYPE_BADGE[node.type] ?? "bg-muted text-muted-foreground"
  const label = TYPE_LABEL[node.type] ?? node.type

  return (
    <li>
      <div className="flex items-center gap-2 py-1">
        <span className="min-w-0 truncate text-sm text-foreground">
          {node.name}
        </span>
        <span
          className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium ${badgeClass}`}
        >
          {label}
        </span>
      </div>
      {node.children.length > 0 && (
        <ul className="ml-4 border-l border-border pl-3">
          {node.children.map((child) => (
            <EntityRow key={child.id} node={child} />
          ))}
        </ul>
      )}
    </li>
  )
}

export function EntityTreePreview({ entities, orgName }: EntityTreePreviewProps) {
  const namedEntities = entities.filter((e) => e.name.trim().length > 0)

  if (namedEntities.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Add your first entity to see the structure
      </p>
    )
  }

  const tree = buildTree(namedEntities)

  return (
    <ul className="space-y-0.5">
      <li>
        <div className="flex items-center gap-2 py-1">
          <Building2 className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          <span className="min-w-0 truncate text-sm font-medium text-foreground">
            {orgName}
          </span>
        </div>
        <ul className="ml-4 border-l border-border pl-3">
          {tree.map((node) => (
            <EntityRow key={node.id} node={node} />
          ))}
        </ul>
      </li>
    </ul>
  )
}
