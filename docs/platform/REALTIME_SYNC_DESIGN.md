# Enterprise Real-Time Sync Architecture (WebSockets)

## Status
**Proposed / Pending Enterprise Phase**

## Objective
To transition FinanceOps from a stateless HTTP polling model to a real-time, multi-player collaborative platform. This ensures that as concurrent user volume scales within a single tenant (e.g., Month-End Close collaboration), data remains perfectly synchronized across all client browsers in real-time, preventing data collisions and eliminating manual refreshes for long-running jobs.

---

## 1. The Core Infrastructure (Backend)

### 1.1 Pub/Sub Message Broker (Redis)
We cannot rely on a single API server to hold WebSocket connections since the backend will be load-balanced across multiple instances.
* **Component:** Redis Pub/Sub channels.
* **Mechanism:** When Node A processes a transaction, it publishes a message to the Redis `tenant_updates` channel. All other Nodes subscribed to that channel receive the message and push it to their respective connected WebSockets.

### 1.2 The WebSocket Gateway
* **Protocol:** `Socket.io` or raw WebSockets (`FastAPI WebSockets` if using Python, or a dedicated Node.js microservice if scaling dynamically).
* **Connection Scope:** Connections must be strictly authenticated using the existing `NextAuth` JWT. 
* **Rooms / Channels:** Upon connection, the client joins a "Room" specific to their `tenant_id` and `entity_id`. They only receive broadcasts relevant to their active contextual workspace.

---

## 2. The Client-Side Implementation (Frontend)

### 2.1 The Connection Provider
* **Component:** `<WebSocketProvider>` wrapping the Next.js `(dashboard)` layout.
* **Behavior:** Establishes the connection upon successful authentication and silently attempts reconnection with exponential backoff if the network drops.

### 2.2 TanStack Query (React Query) Integration
Instead of refactoring the UI components to hold local WebSocket state, the WebSocket will simply act as a **Query Invalidator**.
* **Flow:**
  1. User B updates Journal `J-123`.
  2. Backend updates DB, publishes to Redis.
  3. WebSocket Gateway pushes event to User A: `{ event: "JOURNAL_UPDATED", payload: { id: "J-123" } }`.
  4. User A's frontend listener intercepts the event and calls: `queryClient.invalidateQueries({ queryKey: ['journals'] })`.
  5. React Query silently fetches the fresh data in the background and patches the UI without a flash or disruption.

---

## 3. Key Use Cases to Solve

### 3.1 Long-Running Async Job Notifications
* **Trigger:** ERP Sync completion, 50k row CSV upload, or Valuation model computation.
* **Event Action:** Push a Toast notification (via `sonner`) to the user: *"Sync Complete: 12,000 rows processed."*

### 3.2 Row-Level Locking (Collision Prevention)
* **Trigger:** User A begins editing an Airlock Queue mismatch.
* **Event Action:** Broadcast `{ event: "ROW_LOCKED", payload: { id: "A-553", user: "Jane" } }`.
* **UI Update:** User B's screen instantly shows a padlock icon and disables the "Edit" button for that specific row, displaying a tooltip: *"Currently being edited by Jane."*

### 3.3 Live Multi-player Presence
* **Trigger:** User enters a specific module (e.g., `/reconciliation`).
* **UI Update:** Show user avatars in the Topbar indicating who else is actively viewing the same module context.

---

## 4. Implementation Steps (Phased Approach)

- **Phase 1: Foundation.** Deploy Redis, build the robust JWT-authenticated connection layer, and implement simple Toast notifications for Async Jobs.
- **Phase 2: Data Freshness.** Wire the WebSocket receiver to `queryClient.invalidateQueries` to automatically refresh React Query tables on external mutation.
- **Phase 3: Multiplayer.** Implement presence indicators and strict Row-Level UI Locking for active edits.
